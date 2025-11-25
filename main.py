from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from api import rooms, players, rounds, websocket

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Chicken Game API",
    description="Backend API for multiplayer game theory teaching platform",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(rooms.router)
app.include_router(players.router)
app.include_router(rounds.router)
app.include_router(websocket.router)


@app.get("/")
def root():
    return {"message": "Chicken Game API", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
