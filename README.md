# availlo-backend

Backend for the Classroom Radar project.

This is a Django REST Framework API for importing university timetables from PDF files, tracking rooms and buildings, and checking whether rooms are free right now based on the active semester timetable.

## Features

- Upload a timetable PDF and extract class sessions using Gemini vision models.
- Normalize extracted venue names and filter out non-permsite locations.
- Create and link `Building`, `Room`, `ClassSession`, and `SessionRoom` records.
- List all rooms.
- Check room status and next session.
- Search rooms by name and show current availability.
- List free rooms at the moment.

## Tech Stack

- Django 6
- Django REST Framework
- SQLite
- `pdf2image` for PDF-to-image conversion
- Google GenAI SDK for timetable extraction

## Project Structure

- `classroom_radar/` - Django project settings and root URL config
- `apps/rooms/` - room listing, room status, search, and availability logic
- `apps/timetable/` - timetable upload and timetable data models

## Setup

1. Create and activate a virtual environment.
2. Install dependencies.
3. Set environment variables.
4. Run migrations.
5. Start the development server.

Example:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Environment Variables

Create a `.env` file in the project root with:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

The project reads `GEMINI_API_KEY` from the environment when uploading PDFs.

## API Endpoints

All endpoints are mounted under `/api/`.

### Rooms

#### `GET /api/rooms/`
Returns all rooms with their building information.

#### `GET /api/rooms/free/`
Returns rooms that are free at the current time.

- Optional query parameter: `building`
- Example: `/api/rooms/free/?building=ELF`

#### `GET /api/rooms/<room_id>/status/`
Returns the current status for a single room, including whether it is free, the current session, and the next session.

#### `GET /api/search/?q=...`
Searches rooms by name and returns matching rooms with their current free/occupied status.

### Timetable

#### `POST /api/timetable/upload/`
Uploads a timetable PDF and extracts class sessions.

Use `multipart/form-data` with:

- `file`: the PDF file
- `semester_id`: the ID of the semester to attach the sessions to

What it does:

1. Converts the PDF pages to images.
2. Sends the images to Gemini for structured extraction.
3. Normalizes venue names.
4. Filters out non-permsite venues `(Currently for univeristy of Uyo,UNIUYO, Akwaibom State)`.
5. Creates `Building` and `Room` rows as needed.
6. Creates one `ClassSession` per extracted class.
7. Links each session to one or more rooms through `SessionRoom`.

## Timetable Import Rules

The import pipeline currently handles these venue rules:

- Non-permsite venues are filtered out.
- `ELF LT` and `ELF` are normalized to `ELF HALL`.
- `LF 3` and `LF 4` are normalized to `FL 3` and `FL 4`.
- `GD 1`, `GD 2`, `GD 3`, and `GD 4` remain GD rooms.
- `NEDUBLK UP` is not kept.
- When a class lists multiple venues, only the allowed venues are saved.

## Current Data Model

### `Semester`

- `name`
- `is_active`

### `ClassSession`

- `semester`
- `course_code`
- `day_of_week`
- `start_time`
- `end_time`
- `level`
- `group`
- `raw_venue_text`
- linked rooms through `SessionRoom`

### `Room`

- `name`
- `building`
- `capacity`

### `Building`

- `code`
- `name`

### `SessionRoom`

Join table linking sessions and rooms.

## How Room Availability Works

Room availability is computed from the active semester timetable, not from a stored boolean field on `Room`.

The logic checks:

- the active semester
- the current day of the week
- the current time
- whether any `ClassSession` is linked to the room through `SessionRoom`

If a session is running now, the room is occupied.
If no session is running, the room is free.
The next session for the day is also returned when available.

## Notes
- The project was being with the context of `Univeristy of Uyo (UNIUYO)` in mind.
- The project uses SQLite by default.

## Development Tips

- If you change the timetable models, run migrations again.
- If you want to clear imported data and re-upload from scratch, delete `ClassSession`, `SessionRoom`, `Room`, and `Building` data first.
- If you add new room naming rules, update the normalization logic in `apps/timetable/views.py`.
