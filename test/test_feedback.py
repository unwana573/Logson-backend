from test.conftest import auth_headers


def _mock_email(monkeypatch):
    """Swaps out the real SendGrid call for a recorder, so tests never hit
    SendGrid and can assert on what would have been sent."""
    sent = []

    def fake_send_email(*, to_email, subject, content):
        sent.append({"to_email": to_email, "subject": subject, "content": content})
        return True

    from app.service import feedback_service

    monkeypatch.setattr(feedback_service, "send_email", fake_send_email)
    return sent


def test_unauthenticated_user_cannot_submit_feedback(client):
    res = client.post("/feedback", json={"message": "Love the store!"})
    assert res.status_code == 401


def test_authenticated_user_can_submit_feedback(client, monkeypatch, admin_token):
    _mock_email(monkeypatch)
    res = client.post("/feedback", json={"message": "Love the store!"}, headers=auth_headers(admin_token))
    assert res.status_code == 201
    assert res.json()["message"] == "Love the store!"
    assert res.json()["user_email"] == "admin@logson.ng"


def test_submitting_feedback_sends_an_email_notification(client, monkeypatch, admin_token):
    sent = _mock_email(monkeypatch)
    client.post("/feedback", json={"message": "Please add PayPal too"}, headers=auth_headers(admin_token))

    assert len(sent) == 1
    assert "Please add PayPal too" in sent[0]["content"]
    assert "admin@logson.ng" in sent[0]["content"]


def test_feedback_still_saves_even_if_email_sending_fails(client, monkeypatch, admin_token):
    from app.service import feedback_service

    monkeypatch.setattr(feedback_service, "send_email", lambda **kwargs: False)

    res = client.post("/feedback", json={"message": "Test resilience"}, headers=auth_headers(admin_token))
    assert res.status_code == 201  # submission succeeds regardless of email outcome


def test_non_admin_cannot_list_feedback(client, monkeypatch, user_token):
    _mock_email(monkeypatch)
    client.post("/feedback", json={"message": "Hi"}, headers=auth_headers(user_token))

    res = client.get("/feedback", headers=auth_headers(user_token))
    assert res.status_code == 403


def test_admin_can_list_all_feedback(client, monkeypatch, admin_token, user_token):
    _mock_email(monkeypatch)
    client.post("/feedback", json={"message": "From admin"}, headers=auth_headers(admin_token))
    client.post("/feedback", json={"message": "From user"}, headers=auth_headers(user_token))

    res = client.get("/feedback", headers=auth_headers(admin_token))
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_empty_feedback_message_is_rejected(client, admin_token):
    res = client.post("/feedback", json={"message": ""}, headers=auth_headers(admin_token))
    assert res.status_code == 422



    