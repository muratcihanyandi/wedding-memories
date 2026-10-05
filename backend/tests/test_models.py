from datetime import timedelta

from app.models import PublicSession, Upload, User, utcnow


def _session(db_engine):
    from app.db import _SessionLocal

    return _SessionLocal()


def test_user_create_and_unique_folder(db_engine):
    with _session(db_engine) as db:
        db.add(User(display_name="Erhan", folder_name="Erhan"))
        db.commit()

        db.add(User(display_name="Erhan", folder_name="Erhan"))
        try:
            db.commit()
            assert False, "ayni klasor adi ikinci kez kaydedilmemeli"
        except Exception:
            db.rollback()


def test_upload_and_session_relations(db_engine):
    with _session(db_engine) as db:
        user = User(display_name="Ayse", folder_name="Ayse")
        db.add(user)
        db.flush()

        upload = Upload(
            user_id=user.id,
            original_filename="IMG_1234.JPG",
            stored_filename="IMG_1234.JPG",
            media_type="image",
            mime_type="image/jpeg",
            size=1024,
            storage_path="Ayse/original/IMG_1234.JPG",
        )
        session = PublicSession(
            token_hash="a" * 64,
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=7),
        )
        db.add_all([upload, session])
        db.commit()

        stored = db.query(Upload).filter_by(user_id=user.id).one()
        assert stored.original_filename == "IMG_1234.JPG"
        assert stored.size == 1024

        ps = db.query(PublicSession).one()
        assert ps.user_id == user.id
