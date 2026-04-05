import traceback
try:
    from app.database import SessionLocal
    from app.models import IngestionStatus
    db = SessionLocal()
    results = db.query(IngestionStatus).all()
    print("Success:", results)
    db.close()
except Exception as e:
    with open("error_full.txt", "w") as f:
        traceback.print_exc(file=f)
    print("ERROR WRITTEN TO error_full.txt")
    print("Error type:", type(e).__name__)
    print("Error message:", str(e)[:2000])
