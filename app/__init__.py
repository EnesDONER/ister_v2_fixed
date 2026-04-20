"""
Flask Uygulaması Başlatma
İster Yönetimi v2 - MVC Mimarisi
"""
from flask import Flask, app
from config import get_config
from app.utils.database import init_db, mysql


def create_app(config_env='development'):
    """
    Flask uygulamasını oluştur ve yapılandır
    
    Args:
        config_env: Konfigürasyon ortamı (development, production, testing)
        
    Returns:
        Flask: Başlatılmış Flask uygulaması
    """
    # Flask uygulamasını oluştur
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    
    # Konfigürasyonu yükle
    config = get_config(config_env)
    app.config.from_object(config)
    
    # Veritabanını başlat
    init_db(app)
    
    # Blueprint'leri (Controller'ları) kayıt et
    _register_blueprints(app)
    
    # Hata işleyicileri
    _register_error_handlers(app)
    
    # Teardown handler'ı kapat - Flask-MySQLdb zaten kendi teardown'ını yönetiyor
    # Bizim ek bir teardown handler'ımız olmasın
    
    return app


def _register_blueprints(app):
    """
    Tüm blueprint'leri (controller'ları) uygulamaya kayıt et
    
    Args:
        app: Flask uygulaması
    """
    # Kimlik doğrulama ve ana sayfa
    from app.controllers.auth import auth_bp
    from app.controllers.main import main_bp
    
    # API'ler
    from app.controllers.platform_api import platform_api_bp
    from app.controllers.config_api import config_api_bp
    from app.controllers.level_api import level_api_bp
    from app.controllers.requirement_api import requirement_api_bp
    from app.controllers.test_api import test_api_bp
    from app.controllers.ta_api import ta_api_bp
    from app.controllers.dashboard_api import dashboard_api_bp
    from app.controllers.comparison_api import comparison_api_bp
    
    from app.controllers.user_api       import user_api_bp
    from app.controllers.audit_log_api  import audit_log_api_bp
    from app.controllers.tablo_api      import tablo_api_bp
    from app.controllers.bullet_api     import bullet_api_bp
    from app.controllers.firma_gorusu_api import firma_gorusu_api_bp
    
    # Sayfa yönlendiricileri
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    
    # API'ler
    app.register_blueprint(platform_api_bp)
    app.register_blueprint(config_api_bp)
    app.register_blueprint(level_api_bp)
    app.register_blueprint(requirement_api_bp)
    app.register_blueprint(test_api_bp)
    app.register_blueprint(ta_api_bp)
    app.register_blueprint(dashboard_api_bp)
    app.register_blueprint(comparison_api_bp)

    app.register_blueprint(user_api_bp)
    app.register_blueprint(audit_log_api_bp)
    app.register_blueprint(tablo_api_bp)
    app.register_blueprint(bullet_api_bp)
    app.register_blueprint(firma_gorusu_api_bp)



def _register_error_handlers(app):
    """
    Hata işleyicileri kayıt et
    
    Args:
        app: Flask uygulaması
    """
    from flask import jsonify, redirect, url_for
    import MySQLdb
    
    @app.errorhandler(MySQLdb.OperationalError)
    def db_operational_error(error):
        """Veritabanı bağlantı hatası"""
        return jsonify({'error': 'Veritabanı bağlantı hatası. Lütfen daha sonra tekrar deneyin.'}), 503
    
    @app.errorhandler(MySQLdb.ProgrammingError)
    def db_programming_error(error):
        """Veritabanı programlama hatası"""
        return jsonify({'error': 'Veritabanı sorgu hatası'}), 500
    
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Sayfa bulunamadı'}, 404
    
    @app.errorhandler(500)
    def server_error(error):
        return {'error': 'Sunucu hatası'}, 500
    
    @app.errorhandler(401)
    def unauthorized(error):
        return redirect(url_for('auth.login'))
