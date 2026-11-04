"""Енгізілген деректерді тексеру (pydantic) және қазақша қате хабарлары."""
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, field_validator, model_validator

from .errors import AppError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _message(err: dict) -> str:
    t, ctx = err["type"], err.get("ctx", {})
    if t == "missing":
        return "Міндетті өріс."
    if t == "string_too_short":
        return f"Кемінде {ctx.get('min_length')} таңба болуы керек."
    if t == "string_too_long":
        return f"Көбі {ctx.get('max_length')} таңба болуы керек."
    if t == "string_pattern_mismatch":
        return "Рұқсат етілмеген таңбалар бар."
    if t in ("int_type", "int_parsing", "string_type", "float_type", "bool_type"):
        return "Дұрыс типтегі мән енгізіңіз (сан немесе мәтін)."
    if t == "greater_than_equal":
        return f"Мәні {ctx.get('ge')}-ден кем болмауы керек."
    if t == "less_than_equal":
        return f"Мәні {ctx.get('le')}-ден артық болмауы керек."
    if t == "literal_error":
        return "Рұқсат етілген мәндердің бірін таңдаңыз."
    if t == "extra_forbidden":
        return "Белгісіз немесе рұқсат етілмеген өріс."
    if t == "value_error":
        return str(ctx.get("error", err["msg"]))
    return err["msg"]


def parse(model, data):
    """Деректерді модель бойынша тексереді. Қате болса, 422 және өріс бойынша тізім қайтарады."""
    try:
        return model.model_validate(data)
    except ValidationError as e:
        details = [{"field": ".".join(str(p) for p in er["loc"]), "message": _message(er)} for er in e.errors()]
        raise AppError(422, "validation_error", "Енгізілген деректерде қате бар.", details) from None


# ---------- Авторизация ----------
class RegisterIn(Base):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_.-]+$")
    email: str = Field(max_length=120)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        if not EMAIL_RE.match(v):
            raise ValueError("Email форматы қате. Мысалы: name@example.com")
        return v.lower()

    @field_validator("password")
    @classmethod
    def _password(cls, v):
        if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
            raise ValueError("Құпиясөзде әріп те, сан да болуы керек.")
        return v


class LoginIn(Base):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=128)


# ---------- Тауарлар ----------
class ProductCreate(Base):
    sku: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="Басқа", min_length=1, max_length=60)
    price: StrictInt = Field(ge=0, le=1_000_000_000)
    min_quantity: StrictInt = Field(default=0, ge=0, le=1_000_000)
    quantity: StrictInt = Field(default=0, ge=0, le=1_000_000)


class ProductUpdate(Base):
    """PUT: барлық өріс міндетті. Қалдық (quantity) тек кіріс/шығыс арқылы өзгереді."""
    sku: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=60)
    price: StrictInt = Field(ge=0, le=1_000_000_000)
    min_quantity: StrictInt = Field(ge=0, le=1_000_000)


class ProductPatch(Base):
    sku: Optional[str] = Field(default=None, min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    category: Optional[str] = Field(default=None, min_length=1, max_length=60)
    price: Optional[StrictInt] = Field(default=None, ge=0, le=1_000_000_000)
    min_quantity: Optional[StrictInt] = Field(default=None, ge=0, le=1_000_000)

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.model_dump(exclude_none=True):
            raise ValueError("Өзгертілетін кемінде бір өрісті жіберіңіз.")
        return self


class MovementIn(Base):
    type: Literal["in", "out"]
    quantity: StrictInt = Field(ge=1, le=1_000_000)


class ProductListQuery(Base):
    search: str = Field(default="", max_length=100)
    low: Literal["0", "1"] = "0"
    limit: int = Field(default=100, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class MovementListQuery(Base):
    limit: int = Field(default=100, ge=1, le=500)


# ---------- Қолданушылар ----------
class RoleIn(Base):
    role: Literal["user", "manager", "admin"]
