import pytest
import json
from unittest.mock import patch, AsyncMock
import uuid


@pytest.mark.asyncio
async def test_generate_notes_success(client):
    """Test successful clinical notes generation from ambient transcription"""
    # First, register and login a user
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Smith", "email": "doctor@example.com", "password": "Password123!"},
        )

    assert register_response.status_code == 201
    user_data = register_response.json()["data"]
    auth_token = user_data["accessToken"]

    # Prepare dummy clinical transcript
    dummy_transcript = (
        "Patient presents with persistent cough for two weeks. "
        "Temperature 99.2F, mild shortness of breath. "
        "Chest X-ray shows minor infiltrates in right lower lobe. "
        "Will prescribe amoxicillin 500mg three times daily for 10 days. "
        "Follow-up in one week. Patient advised to rest and stay hydrated."
    )

    # Mock the LLM response for clinical notes
    mock_llm_response = {
        "subjective": "Patient-reported persistent cough for two weeks, mild shortness of breath",
        "objective": "Temperature 99.2F, Chest X-ray shows minor infiltrates in right lower lobe",
        "assessment": "Probable acute bronchitis",
        "plan": "Amoxicillin 500mg three times daily for 10 days, rest, hydration, follow-up in one week",
        "medications": ["Amoxicillin 500mg"],
        "follow_up": "One week follow-up appointment"
    }

    with patch("src.domain.scribe.service._call_llm", new_callable=AsyncMock, return_value=mock_llm_response):
        response = await client.post(
            "/api/v1/scribe/generate",
            json={"text": dummy_transcript, "note_type": "clinical"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data

    session = data["data"]
    assert session["type"] == "generate"
    assert session["status"] == "completed"
    assert session["result"]["subjective"] == "Patient-reported persistent cough for two weeks, mild shortness of breath"
    assert session["result"]["assessment"] == "Probable acute bronchitis"


@pytest.mark.asyncio
async def test_generate_notes_missing_text(client):
    """Test generate_notes with missing required text field"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Jones", "email": "jones@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    response = await client.post(
        "/api/v1/scribe/generate",
        json={"text": "", "note_type": "clinical"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "text" in data["message"] or "empty" in data["message"]


@pytest.mark.asyncio
async def test_generate_notes_invalid_note_type(client):
    """Test generate_notes with invalid note_type"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Brown", "email": "brown@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    response = await client.post(
        "/api/v1/scribe/generate",
        json={"text": "Some clinical text", "note_type": "invalid_type"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_generate_notes_unauthorized(client):
    """Test generate_notes without authentication"""
    dummy_transcript = "Patient presents with symptoms..."

    response = await client.post(
        "/api/v1/scribe/generate",
        json={"text": dummy_transcript, "note_type": "clinical"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_summarize_success(client):
    """Test successful text summarization"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. White", "email": "white@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    long_text = (
        "A 45-year-old female patient came in for a routine checkup. "
        "She reported feeling tired and having occasional headaches for the past month. "
        "Physical examination revealed normal vital signs. Blood pressure was 120/80. "
        "Heart rate was 72 bpm. Lungs were clear. "
        "We ordered comprehensive blood work which came back normal. "
        "Recommended increased water intake, regular exercise, and sleep schedule optimization. "
        "Patient to follow up in 6 weeks."
    )

    mock_summary = {
        "summary": "45-year-old female with fatigue and headaches, normal exam and labs, advised lifestyle changes.",
        "key_points": [
            "Normal vital signs",
            "Normal blood work",
            "Recommended water intake, exercise, sleep optimization",
            "6-week follow-up scheduled"
        ],
        "entities": {
            "medications": [],
            "conditions": ["fatigue", "headaches"],
            "procedures": ["blood work"]
        },
        "word_count": 92
    }

    with patch("src.domain.scribe.service._call_llm", new_callable=AsyncMock, return_value=mock_summary):
        response = await client.post(
            "/api/v1/scribe/summarize",
            json={"text": long_text},
            headers={"Authorization": f"Bearer {auth_token}"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    session = data["data"]
    assert session["type"] == "summarize"
    assert session["status"] == "completed"
    assert "fatigue" in session["result"]["entities"]["conditions"]


@pytest.mark.asyncio
async def test_scribe_history(client):
    """Test retrieving scribe session history"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Green", "email": "green@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    # Create multiple scribe sessions
    mock_response = {"title": "Test", "sections": [], "action_items": [], "summary": "Test"}

    with patch("src.domain.scribe.service._call_llm", new_callable=AsyncMock, return_value=mock_response):
        for i in range(3):
            await client.post(
                "/api/v1/scribe/generate",
                json={"text": f"Test transcript {i}", "note_type": "general"},
                headers={"Authorization": f"Bearer {auth_token}"}
            )

    # Retrieve history
    response = await client.get(
        "/api/v1/scribe/history",
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) == 3


@pytest.mark.asyncio
async def test_scribe_get_session(client):
    """Test retrieving a specific scribe session"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Blue", "email": "blue@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    mock_response = {
        "subjective": "Test subjective",
        "objective": "Test objective",
        "assessment": "Test assessment",
        "plan": "Test plan",
        "medications": [],
        "follow_up": "Test follow-up"
    }

    with patch("src.domain.scribe.service._call_llm", new_callable=AsyncMock, return_value=mock_response):
        create_response = await client.post(
            "/api/v1/scribe/generate",
            json={"text": "Test transcript", "note_type": "clinical"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )

    session_id = create_response.json()["data"]["id"]

    # Retrieve specific session
    response = await client.get(
        f"/api/v1/scribe/{session_id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == session_id
    assert data["data"]["status"] == "completed"


@pytest.mark.asyncio
async def test_scribe_get_session_not_found(client):
    """Test retrieving non-existent scribe session"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Red", "email": "red@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]
    fake_id = str(uuid.uuid4())

    response = await client.get(
        f"/api/v1/scribe/{fake_id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_scribe_get_session_forbidden(client):
    """Test accessing another user's scribe session"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        # Create first user and session
        register_response_1 = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Purple", "email": "purple@example.com", "password": "Password123!"},
        )
        auth_token_1 = register_response_1.json()["data"]["accessToken"]

        mock_response = {"title": "Test", "sections": [], "action_items": [], "summary": "Test"}
        with patch("src.domain.scribe.service._call_llm", new_callable=AsyncMock, return_value=mock_response):
            create_response = await client.post(
                "/api/v1/scribe/generate",
                json={"text": "Test transcript", "note_type": "general"},
                headers={"Authorization": f"Bearer {auth_token_1}"}
            )

        session_id = create_response.json()["data"]["id"]

        # Create second user
        register_response_2 = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Orange", "email": "orange@example.com", "password": "Password123!"},
        )
        auth_token_2 = register_response_2.json()["data"]["accessToken"]

        # Try to access first user's session with second user's token
        response = await client.get(
            f"/api/v1/scribe/{session_id}",
            headers={"Authorization": f"Bearer {auth_token_2}"}
        )

        assert response.status_code == 403


@pytest.mark.asyncio
async def test_generate_notes_llm_failure(client):
    """Test handling of LLM API failures"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Yellow", "email": "yellow@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    with patch("src.domain.scribe.service._call_llm", side_effect=Exception("API Error")):
        response = await client.post(
            "/api/v1/scribe/generate",
            json={"text": "Test transcript", "note_type": "clinical"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )

    # Should still return 200 but with failed status
    assert response.status_code == 200
    data = response.json()
    session = data["data"]
    assert session["status"] == "failed"
    assert session["result"] is None


# ========== NEW TRANSCRIPTION TESTS ==========


@pytest.mark.asyncio
async def test_transcribe_success(client):
    """Test successful audio transcription with speaker diarization"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Audio", "email": "audio@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    # Mock audio bytes and transcription results
    mock_raw_transcript = "What brings you in today? Chest pain for three days. Let me examine you."

    mock_diarization = {
        "segments": [
            {"speaker": "Doctor", "text": "What brings you in today?"},
            {"speaker": "Patient", "text": "Chest pain for three days."},
            {"speaker": "Doctor", "text": "Let me examine you."},
        ]
    }

    with patch(
        "src.core.transcription.LocalWhisperProvider.transcribe",
        new_callable=AsyncMock,
        return_value=mock_raw_transcript,
    ), patch(
        "src.domain.scribe.service._call_llm", new_callable=AsyncMock, return_value=mock_diarization
    ):
        # Valid WebM magic bytes (EBML header) followed by fake content
        audio_data = b"\x1a\x45\xdf\xa3" + b"fake webm content"
        response = await client.post(
            "/api/v1/scribe/transcribe",
            files={"audio": ("test.webm", audio_data, "audio/webm")},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "segments" in data["data"]
    assert len(data["data"]["segments"]) == 3
    assert data["data"]["segments"][0]["speaker"] == "Doctor"
    assert "full_text" in data["data"]


@pytest.mark.asyncio
async def test_transcribe_invalid_format(client):
    """Test transcribe with unsupported MIME type"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Format", "email": "format@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    audio_data = b"fake content"
    response = await client.post(
        "/api/v1/scribe/transcribe",
        files={"audio": ("test.txt", audio_data, "text/plain")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "INVALID_AUDIO_FORMAT" in data.get("code", "")


@pytest.mark.asyncio
async def test_transcribe_invalid_magic_bytes(client):
    """Test transcribe rejects invalid magic bytes even with correct MIME type"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Bytes", "email": "bytes@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    # WebM MIME type but invalid magic bytes
    fake_audio = b"not real webm content"
    response = await client.post(
        "/api/v1/scribe/transcribe",
        files={"audio": ("test.webm", fake_audio, "audio/webm")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 400
    data = response.json()
    assert "INVALID_AUDIO_FORMAT" in data.get("code", "")


@pytest.mark.asyncio
async def test_transcribe_file_too_large(client):
    """Test transcribe with file exceeding 25MB limit"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Large", "email": "large@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    # Create audio data larger than 25MB
    large_audio = b"x" * (26 * 1024 * 1024)
    response = await client.post(
        "/api/v1/scribe/transcribe",
        files={"audio": ("test.webm", large_audio, "audio/webm")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 413
    data = response.json()
    assert data["success"] is False
    assert "PAYLOAD_TOO_LARGE" in data.get("code", "")


# ========== NEW DOCTOR ANSWERS TESTS ==========


@pytest.mark.asyncio
async def test_doctor_answers_success(client):
    """Test saving doctor's MCQ answers to a session"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Answers", "email": "answers@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    # Create a clinical notes session with suggestions
    mock_response = {
        "subjective": "Patient reports chest pain",
        "objective": "Temp 98.6F, BP 120/80",
        "assessment": "Possible angina",
        "plan": "EKG and cardiology consult",
        "medications": [],
        "follow_up": "Cardiology follow-up",
        "suggestions": [
            {
                "id": "sugg-1",
                "question": "Did you hear any abnormal lung sounds?",
                "options": ["Clear", "Crackles", "Wheezing", "Other"],
                "category": "observation",
            },
            {
                "id": "sugg-2",
                "question": "Recommend stress test?",
                "options": ["Yes", "No", "Consider later", "Not needed"],
                "category": "plan",
            },
        ],
    }

    with patch("src.domain.scribe.service._call_llm", new_callable=AsyncMock, return_value=mock_response):
        create_response = await client.post(
            "/api/v1/scribe/generate",
            json={"text": "Patient with chest pain", "note_type": "clinical"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    session_id = create_response.json()["data"]["id"]

    # Save doctor answers
    answers_payload = {
        "answers": [
            {"suggestion_id": "sugg-1", "selected_option": "Crackles", "custom_answer": ""},
            {"suggestion_id": "sugg-2", "selected_option": "Yes", "custom_answer": ""},
        ]
    }

    response = await client.post(
        f"/api/v1/scribe/{session_id}/doctor-answers",
        json=answers_payload,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "doctor_answers" in data["data"]
    assert len(data["data"]["doctor_answers"]) == 2
    assert data["data"]["doctor_answers"][0]["selected_option"] == "Crackles"


@pytest.mark.asyncio
async def test_doctor_answers_invalid_id(client):
    """Test saving doctor answers with non-existent suggestion ID"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Invalid", "email": "invalid@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    mock_response = {
        "subjective": "Test",
        "objective": "Test",
        "assessment": "Test",
        "plan": "Test",
        "medications": [],
        "follow_up": "Test",
        "suggestions": [{"id": "sugg-1", "question": "Test?", "options": [], "category": "observation"}],
    }

    with patch("src.domain.scribe.service._call_llm", new_callable=AsyncMock, return_value=mock_response):
        create_response = await client.post(
            "/api/v1/scribe/generate",
            json={"text": "Test", "note_type": "clinical"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    session_id = create_response.json()["data"]["id"]

    # Try to save with invalid suggestion ID
    answers_payload = {"answers": [{"suggestion_id": "invalid-id", "selected_option": "Option", "custom_answer": ""}]}

    response = await client.post(
        f"/api/v1/scribe/{session_id}/doctor-answers",
        json=answers_payload,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 400
    data = response.json()
    assert "INVALID_SUGGESTION_ID" in data.get("code", "")


# ========== NEW SESSION UPDATE/DELETE TESTS ==========


@pytest.mark.asyncio
async def test_update_session_title(client):
    """Test updating session title"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Update", "email": "update@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    mock_response = {"title": "Original", "sections": [], "action_items": [], "summary": "Test"}

    with patch("src.domain.scribe.service._call_llm", new_callable=AsyncMock, return_value=mock_response):
        create_response = await client.post(
            "/api/v1/scribe/generate",
            json={"text": "Test text", "note_type": "general"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    session_id = create_response.json()["data"]["id"]

    # Update title
    update_payload = {"title": "Updated Title"}

    response = await client.patch(
        f"/api/v1/scribe/{session_id}",
        json=update_payload,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_update_session_result_merge(client):
    """Test updating session result fields with partial merge"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Merge", "email": "merge@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    mock_response = {
        "subjective": "Original subjective",
        "objective": "Original objective",
        "assessment": "Original assessment",
        "plan": "Original plan",
        "medications": ["Med1"],
        "follow_up": "Original follow-up",
    }

    with patch("src.domain.scribe.service._call_llm", new_callable=AsyncMock, return_value=mock_response):
        create_response = await client.post(
            "/api/v1/scribe/generate",
            json={"text": "Test", "note_type": "clinical"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    session_id = create_response.json()["data"]["id"]

    # Update only subjective field
    update_payload = {"result": {"subjective": "Updated subjective"}}

    response = await client.patch(
        f"/api/v1/scribe/{session_id}",
        json=update_payload,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["result"]["subjective"] == "Updated subjective"
    # Other fields should remain unchanged
    assert data["data"]["result"]["objective"] == "Original objective"
    assert data["data"]["result"]["medications"] == ["Med1"]


@pytest.mark.asyncio
async def test_delete_session(client):
    """Test hard delete of a session"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Delete", "email": "delete@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    mock_response = {"title": "Test", "sections": [], "action_items": [], "summary": "Test"}

    with patch("src.domain.scribe.service._call_llm", new_callable=AsyncMock, return_value=mock_response):
        create_response = await client.post(
            "/api/v1/scribe/generate",
            json={"text": "Test", "note_type": "general"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    session_id = create_response.json()["data"]["id"]

    # Delete session
    response = await client.delete(
        f"/api/v1/scribe/{session_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 204

    # Verify session is deleted
    response = await client.get(
        f"/api/v1/scribe/{session_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_notes_with_suggestions(client):
    """Test that clinical notes include suggestions array"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Suggest", "email": "suggest@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    mock_soap_response = {
        "subjective": "Patient reports fever",
        "objective": "Temp 101.5F",
        "assessment": "Acute viral infection",
        "plan": "Rest, fluids, antipyretics",
        "medications": ["Acetaminophen"],
        "follow_up": "3-day follow-up",
    }

    mock_suggestions_response = {
        "suggestions": [
            {
                "id": "sugg-1",
                "question": "Did you observe any rash?",
                "options": ["No rash", "Localized rash", "Generalized rash", "Rash with fever"],
                "category": "observation",
            }
        ]
    }

    # Use side_effect with list: first call returns SOAP, second call returns suggestions
    mock_llm = AsyncMock(side_effect=[mock_soap_response, mock_suggestions_response])

    with patch("src.domain.scribe.service._call_llm", mock_llm):
        response = await client.post(
            "/api/v1/scribe/generate",
            json={"text": "Patient with fever", "note_type": "clinical"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    assert response.status_code == 200
    data = response.json()
    result = data["data"]["result"]
    assert "suggestions" in result
    assert len(result["suggestions"]) > 0
    assert result["suggestions"][0]["id"] == "sugg-1"


@pytest.mark.asyncio
async def test_transcribe_chunk_success(client):
    """Test real-time audio chunk transcription (no diarization, fast path)"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Chunk", "email": "chunk@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    mock_chunk_transcript = "Patient reports chest pain for three days."

    with patch(
        "src.core.transcription.LocalWhisperProvider.transcribe_chunk",
        new_callable=AsyncMock,
        return_value=mock_chunk_transcript,
    ):
        audio_data = b"\x1a\x45\xdf\xa3" + b"fake webm chunk content"
        response = await client.post(
            "/api/v1/scribe/transcribe/chunk",
            files={"audio": ("chunk.webm", audio_data, "audio/webm")},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "text" in data["data"]
    assert data["data"]["text"] == mock_chunk_transcript


@pytest.mark.asyncio
async def test_transcribe_chunk_invalid_format(client):
    """Test chunk transcription rejects non-audio files"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. ChunkFmt", "email": "chunkfmt@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    response = await client.post(
        "/api/v1/scribe/transcribe/chunk",
        files={"audio": ("chunk.txt", b"not audio", "text/plain")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 400
    data = response.json()
    assert "INVALID_AUDIO_FORMAT" in data.get("code", "")


@pytest.mark.asyncio
async def test_generate_notes_polymorphic_medications(client):
    """Test that medications can be returned as strings OR structured objects"""
    with patch("src.domain.auth.service.send_verification_email", new_callable=AsyncMock):
        register_response = await client.post(
            "/api/v1/auth/register",
            json={"name": "Dr. Poly", "email": "poly@example.com", "password": "Password123!"},
        )

    auth_token = register_response.json()["data"]["accessToken"]

    # Mock response with polymorphic medications: some strings, some objects
    mock_response = {
        "subjective": "Patient with hypertension",
        "objective": "BP 160/100",
        "assessment": "Hypertension stage 2",
        "plan": "Pharmacotherapy and lifestyle changes",
        "medications": [
            "Aspirin 500mg oral",  # string format
            {"name": "Lisinopril", "dosage": "10mg", "route": "oral"},  # object format
            "Atorvastatin 20mg oral",  # string format
        ],
        "action_items": [
            "Schedule follow-up in 2 weeks",
            {"text": "Run lipid panel"},
        ],
        "follow_up": "2-week follow-up",
    }

    with patch("src.domain.scribe.service._call_llm", new_callable=AsyncMock, return_value=mock_response):
        response = await client.post(
            "/api/v1/scribe/generate",
            json={"text": "Patient with hypertension", "note_type": "clinical"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

    assert response.status_code == 200
    data = response.json()
    result = data["data"]["result"]

    # Verify medications are returned with mixed types
    assert len(result["medications"]) == 3
    assert isinstance(result["medications"][0], str)  # Aspirin as string
    assert isinstance(result["medications"][1], dict)  # Lisinopril as object
    assert result["medications"][1]["name"] == "Lisinopril"
    assert isinstance(result["medications"][2], str)  # Atorvastatin as string

    # Verify action items also support polymorphic types
    assert len(result["action_items"]) == 2
    assert isinstance(result["action_items"][0], str)
    assert isinstance(result["action_items"][1], dict)
    assert result["action_items"][1]["text"] == "Run lipid panel"
