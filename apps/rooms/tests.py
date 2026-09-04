from io import BytesIO
from unittest.mock import patch

import cloudinary
from cloudinary import CloudinaryResource
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.rooms.models import Building, Room


def _tiny_png_bytes():
    buf = BytesIO()
    Image.new("RGB", (1, 1), "red").save(buf, format="PNG")
    return buf.getvalue()


class AdminRoomCRUDTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Dummy cloudinary config so CloudinaryResource.url can build without env creds.
        cloudinary.config(cloud_name="testcloud", api_key="key", api_secret="secret")

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="pass12345", is_staff=True
        )
        self.admin_token = Token.objects.create(user=self.admin)
        self.user = User.objects.create_user(username="bob", password="pass12345")
        self.user_token = Token.objects.create(user=self.user)
        self.building = Building.objects.create(name="New Engineering Block", code="NECB")
        self.list_url = reverse("admin-room-list")

    def auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")

    # ---- listing / search / filter / pagination ----

    def test_list_paginates_at_10(self):
        for i in range(12):
            Room.objects.create(name=f"Room {i}", building=self.building)
        self.auth_admin()
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 12)
        self.assertEqual(len(resp.data["results"]), 10)
        resp2 = self.client.get(self.list_url, {"page": 2})
        self.assertEqual(len(resp2.data["results"]), 2)

    def test_search_by_name(self):
        other = Building.objects.create(name="Physics Block", code="PHY")
        Room.objects.create(name="NECB 1", building=self.building)
        Room.objects.create(name="Physics Lab", building=other)
        self.auth_admin()
        resp = self.client.get(self.list_url, {"search": "necb"})
        names = [r["name"] for r in resp.data["results"]]
        self.assertEqual(names, ["NECB 1"])

    def test_search_by_building_name_and_code(self):
        other = Building.objects.create(name="Science Complex", code="SCI")
        Room.objects.create(name="Room A", building=self.building)
        Room.objects.create(name="Room B", building=other)
        self.auth_admin()
        by_name = self.client.get(self.list_url, {"search": "Engineering Block"})
        self.assertEqual([r["name"] for r in by_name.data["results"]], ["Room A"])
        by_code = self.client.get(self.list_url, {"search": "SCI"})
        self.assertEqual([r["name"] for r in by_code.data["results"]], ["Room B"])

    def test_faculty_filter_is_case_insensitive(self):
        Room.objects.create(name="Room A", building=self.building, faculty="Engineering")
        Room.objects.create(name="Room B", building=self.building, faculty="Science")
        self.auth_admin()
        resp = self.client.get(self.list_url, {"faculty": "engineering"})
        self.assertEqual([r["name"] for r in resp.data["results"]], ["Room A"])

    # ---- create ----

    def test_create_without_image(self):
        self.auth_admin()
        resp = self.client.post(
            self.list_url,
            {
                "name": "NECB 1",
                "building": self.building.id,
                "faculty": "Engineering",
                "capacity": 50,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["slug"], "necb-1")
        self.assertEqual(resp.data["building"]["code"], "NECB")
        self.assertEqual(resp.data["full_name"], "NONE")  # default

    @patch("cloudinary.uploader.upload_resource")
    def test_create_with_image_uploads_and_returns_url(self, mock_upload):
        mock_upload.return_value = CloudinaryResource(
            public_id="rooms/test", format="png", version="1",
            type="upload", resource_type="image",
        )
        self.auth_admin()
        image = SimpleUploadedFile("t.png", _tiny_png_bytes(), content_type="image/png")
        resp = self.client.post(
            self.list_url,
            {"name": "NECB 1", "building": self.building.id, "image": image},
            format="multipart",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        mock_upload.assert_called_once()
        self.assertIn("rooms/test", resp.data["image"])
        self.assertTrue(resp.data["image"].startswith("http"))

    def test_slug_collision_gets_suffix(self):
        self.auth_admin()
        first = self.client.post(self.list_url, {"name": "NECB 1"}, format="json")
        second = self.client.post(self.list_url, {"name": "NECB 1"}, format="json")
        self.assertEqual(first.data["slug"], "necb-1")
        self.assertEqual(second.data["slug"], "necb-1-2")

    # ---- update / delete by slug ----

    def test_rename_regenerates_slug(self):
        room = Room.objects.create(name="NECB 1", building=self.building)
        self.assertEqual(room.slug, "necb-1")
        self.auth_admin()
        detail = reverse("admin-room-detail", kwargs={"slug": "necb-1"})
        resp = self.client.patch(detail, {"name": "NECB 2"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["slug"], "necb-2")
        # new slug resolves, old one 404s
        self.assertEqual(
            self.client.get(reverse("admin-room-detail", kwargs={"slug": "necb-2"})).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.get(reverse("admin-room-detail", kwargs={"slug": "necb-1"})).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_delete_by_slug(self):
        Room.objects.create(name="NECB 1", building=self.building)
        self.auth_admin()
        detail = reverse("admin-room-detail", kwargs={"slug": "necb-1"})
        resp = self.client.delete(detail)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Room.objects.filter(slug="necb-1").exists())

    # ---- auth / permissions ----

    def test_non_admin_is_forbidden(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user_token.key}")
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.post(self.list_url, {"name": "X"}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_anonymous_is_unauthorized(self):
        self.assertEqual(self.client.get(self.list_url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_login_returns_token(self):
        resp = self.client.post(
            reverse("api-token-auth"),
            {"username": "admin", "password": "pass12345"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["token"], self.admin_token.key)


class PublicReadRegressionTests(APITestCase):
    def setUp(self):
        self.building = Building.objects.create(name="New Engineering Block", code="NECB")
        self.room = Room.objects.create(
            name="NECB 1", building=self.building, faculty="Engineering"
        )

    def test_public_list_still_open(self):
        resp = self.client.get(reverse("room-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_public_detail_exposes_new_fields(self):
        resp = self.client.get(reverse("room-detail", kwargs={"slug": "necb-1"}))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("full_name", resp.data)
        self.assertIn("faculty", resp.data)
        self.assertEqual(resp.data["faculty"], "Engineering")
        self.assertIsNone(resp.data["image"])  # no image -> null (not a raw storage string)
