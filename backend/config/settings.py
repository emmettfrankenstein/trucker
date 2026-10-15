"""Django settings, configured from environment variables (see .env.example)."""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
)
environ.Env.read_env(BASE_DIR.parent / ".env")
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-only-insecure-key-change-me-in-production")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "accounts",
    "trips",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)

REDIS_URL = env("REDIS_URL", default="")
CACHES = {
    "default": (
        {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}
        if REDIS_URL
        else {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "trucker"}
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", default="300/hour"),
        "user": env("THROTTLE_USER", default="1000/hour"),
        "plan": env("THROTTLE_PLAN", default="30/hour"),
        "geocode": env("THROTTLE_GEOCODE", default="600/hour"),
    },
    "EXCEPTION_HANDLER": "config.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Trucker: Weather-Aware Truck Routing API",
    "DESCRIPTION": "Plan truck routes scored by forecast weather risk at each checkpoint's ETA.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --- Domain configuration ---------------------------------------------------------------
TOMTOM_API_KEY = env("TOMTOM_API_KEY", default="")
GEOCODE_COUNTRIES = env("GEOCODE_COUNTRIES", default="US,CA,MX")
WEATHER_CACHE_SECONDS = env.int("WEATHER_CACHE_SECONDS", default=30 * 60)
GEOCODE_CACHE_SECONDS = env.int("GEOCODE_CACHE_SECONDS", default=24 * 3600)
# Classify wind on sustained speed (as the brief's table reads) or on gusts.
RISK_WIND_FIELD = env("RISK_WIND_FIELD", default="sustained")
HEATMAP_HOURS = 48
HEATMAP_BUFFER_MI = env.float("HEATMAP_BUFFER_MI", default=30.0)
HEATMAP_MAX_CELLS = env.int("HEATMAP_MAX_CELLS", default=250)
# Open-Meteo's free tier allows ~600 locations/minute. A trip's checkpoints and its heatmap
# are requested back to back, so their per-request caps together stay under that.
OPEN_METEO_API_KEY = env("OPEN_METEO_API_KEY", default="")
OPEN_METEO_LOCATIONS_PER_MINUTE = env.int("OPEN_METEO_LOCATIONS_PER_MINUTE", default=580)
OPEN_METEO_LOCATIONS_PER_HOUR = env.int("OPEN_METEO_LOCATIONS_PER_HOUR", default=4800)
OPEN_METEO_LOCATIONS_PER_DAY = env.int("OPEN_METEO_LOCATIONS_PER_DAY", default=9500)
# Weather sources in order; each fills the points the ones before it could not. NWS covers
# the US only; MET Norway is global; Open-Meteo is a last resort because its free quota is
# counted per IP and Render's outbound IPs are shared with other apps.
WEATHER_PROVIDER_CHAIN = env.list(
    "WEATHER_PROVIDER_CHAIN",
    default=["providers.nws.NwsWeather", "providers.metno.MetNoWeather", "providers.openmeteo.OpenMeteoWeather"],
)
NWS_MAX_LOCATIONS = env.int("NWS_MAX_LOCATIONS", default=120)
NWS_WORKERS = env.int("NWS_WORKERS", default=8)
MET_NO_MAX_LOCATIONS = env.int("MET_NO_MAX_LOCATIONS", default=120)
MET_NO_WORKERS = env.int("MET_NO_WORKERS", default=6)
OPEN_METEO_MAX_LOCATIONS_PER_REQUEST = env.int("OPEN_METEO_MAX_LOCATIONS_PER_REQUEST", default=300)
MAX_DEPARTURE_DAYS_AHEAD = 7

PROVIDERS = {
    "routing": env("ROUTING_PROVIDER", default="providers.tomtom.TomTomRouting"),
    "geocoding": env("GEOCODING_PROVIDER", default="providers.tomtom.TomTomGeocoding"),
    "weather": env("WEATHER_PROVIDER", default="providers.fallback.FallbackWeather"),
}

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}
