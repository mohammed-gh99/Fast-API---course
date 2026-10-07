from fastapi import FastAPI,HTTPException,Depends,Query
from pydantic import BaseModel,Field as PydanticField
from sqlmodel import SQLModel , Field , Session , create_engine , select
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone
import jwt
from jwt.exceptions import InvalidTokenError
import os
from dotenv import load_dotenv


app = FastAPI()
password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


class Token(BaseModel):
    access_token: str
    token_type: str

class JokeDB(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    author: str
    joke: str
    source: str

class UserDB(SQLModel, table=True):
    id:int | None = Field(default=None, primary_key=True)
    username:str
    password_hash:str
    role:str

class JokePublic(BaseModel):
    id: int
    author: str
    joke: str
    source: str

class JokeUpdate(BaseModel):
    author: str | None = None
    joke: str | None = None
    source: str | None = None

class UserPublic(BaseModel):
    id: int
    username: str
    role: str

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=True)

SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
    
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15) 
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@app.post("/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session)
) -> Token:

    statement = select(UserDB).where(
        UserDB.username == form_data.username
    )

    db_user = session.exec(statement).first()

    if not db_user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
        )

    if not password_hash.verify(
        form_data.password,
        db_user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
        )

    access_token_expires = timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    access_token = create_access_token(
        data={
            "sub": db_user.username
        },
        expires_delta=access_token_expires
    )

    return Token(
        access_token=access_token,
        token_type="bearer"
    )
async def get_current_user(token: str = Depends(oauth2_scheme),session: Session = Depends(get_session)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")
        
        if username is None:
            raise credentials_exception

    except InvalidTokenError:
        raise credentials_exception
    statement = select(UserDB).where(UserDB.username == username)
    db_user = session.exec(statement).first()
    if db_user is None:
        raise credentials_exception

    return db_user

async def require_admin(current_user = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions"
        )

    return current_user

@app.get("/users/me", response_model=UserPublic)
async def read_users_me(
    current_user = Depends(get_current_user)
):
    return current_user

class Joke(BaseModel):
    author: str = PydanticField(min_length=3, max_length=80)
    joke: str = PydanticField(min_length=10, max_length=500)
    source: str = PydanticField(min_length=3, max_length=100)

class MessageResponse(BaseModel):
    message: str



@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/jokes", response_model=list[JokePublic])
async def get_jokes(author:str | None = None,
                    skip: int = Query(default=0, ge=0)  ,
                    limit: int | None = Query(default=None, ge=1, le=100)  ,
                    session: Session = Depends(get_session),
                    current_user = Depends(get_current_user)):
    statement = select(JokeDB)
    statement = statement.order_by(JokeDB.id.desc())
    if author:
        statement = statement.where(JokeDB.author.contains(author))
    statement = statement.offset(skip)
    if limit is not None:
        statement = statement.limit(limit)
        
    results = session.exec(statement)
    jokes = results.all()
    return jokes


@app.get("/jokes/{joke_id}", response_model=JokePublic)
async def get_joke(joke_id: int , session: Session = Depends(get_session),current_user = Depends(get_current_user)):
    statement = select(JokeDB).where(JokeDB.id == joke_id)  
    results = session.exec(statement)
    joke = results.first()
    if joke:
        return joke
    raise HTTPException(status_code=404, detail="Joke not found")

@app.post("/jokes/bulk", response_model=list[JokePublic])
async def create_jokes(jokes: list[Joke], session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    db_jokes = []
    for joke in jokes:
        db_joke = JokeDB(
            author=joke.author,
            joke=joke.joke,
            source=joke.source
        )
        db_jokes.append(db_joke)
    session.add_all(db_jokes)
    session.commit()
    for db_joke in db_jokes:
        session.refresh(db_joke)
    return db_jokes

@app.put("/jokes/{joke_id}", response_model=JokePublic)
async def update_joke(joke_id: int, joke: Joke, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    statement = select(JokeDB).where(JokeDB.id == joke_id)
    results = session.exec(statement)
    existing_joke = results.first()
    if existing_joke:
        existing_joke.author = joke.author
        existing_joke.joke = joke.joke
        existing_joke.source = joke.source
        session.add(existing_joke)
        session.commit()
        session.refresh(existing_joke)
        return existing_joke
    raise HTTPException(status_code=404, detail="Joke not found")

@app.patch("/jokes/{joke_id}", response_model=JokePublic)
async def partial_update_joke(joke_id: int, joke_update: JokeUpdate, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    statement = select(JokeDB).where(JokeDB.id == joke_id)
    results = session.exec(statement)
    existing_joke = results.first()
    if existing_joke:
        update_data = joke_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(existing_joke, key, value)

        session.add(existing_joke)
        session.commit()
        session.refresh(existing_joke)
        return existing_joke
    raise HTTPException(status_code=404, detail="Joke not found")

@app.delete("/jokes/{joke_id}", response_model=MessageResponse)
async def delete_joke(joke_id: int, session: Session = Depends(get_session), current_user = Depends(require_admin)):
    statement = select(JokeDB).where(JokeDB.id == joke_id)
    results = session.exec(statement)
    existing_joke = results.first()
    if existing_joke:
        session.delete(existing_joke)
        session.commit()
        return {"message": "Joke deleted successfully"}
    raise HTTPException(status_code=404, detail="Joke not found")