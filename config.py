"""
Uygulama Konfigürasyonu
İster Yönetimi v2 - Ortamlar
"""
import os
from datetime import timedelta


class Config:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ister_v2_secret_2024'
    DEBUG = False
    TESTING = False

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # MySQL — Lokal veritabanı ayarları
    MYSQL_HOST     = os.environ.get('MYSQL_HOST')     or 'localhost'
    MYSQL_USER     = os.environ.get('MYSQL_USER')     or 'root'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or '1234'
    MYSQL_DB       = os.environ.get('MYSQL_DB')       or 'ister_v2'
    MYSQL_CHARSET  = 'utf8mb4'

    LOG_LEVEL = 'INFO'


class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    LOG_LEVEL = 'WARNING'


class TestingConfig(Config):
    TESTING = True
    DEBUG = True


config_dict = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'testing':     TestingConfig,
    'default':     DevelopmentConfig
}


def get_config(env=None):
    if env is None:
        env = os.environ.get('FLASK_ENV', 'development')
    return config_dict.get(env, config_dict['default'])
