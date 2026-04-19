"""
Veritabanı Bağlantısı ve İşlemleri
"""
from flask_mysqldb import MySQL
import MySQLdb.cursors

# Global MySQL nesnesi
mysql = MySQL()


def init_db(app):
    """
    Veritabanını uygulamaya bağla
    
    Args:
        app: Flask uygulaması
    """
    # MySQL konfigürasyonunu app'e ekle
    app.config['MYSQL_HOST'] = app.config.get('MYSQL_HOST', 'localhost')
    app.config['MYSQL_USER'] = app.config.get('MYSQL_USER', 'root')
    app.config['MYSQL_PASSWORD'] = app.config.get('MYSQL_PASSWORD', '1234')
    app.config['MYSQL_DB'] = app.config.get('MYSQL_DB', 'ister_v2')
    app.config['MYSQL_CHARSET'] = app.config.get('MYSQL_CHARSET', 'utf8mb4')
    
    # MySQL'i uygulamayla bağla
    mysql.init_app(app)


def get_dict_cursor():
    """Sözlük imleçi döndür"""
    return mysql.connection.cursor(MySQLdb.cursors.DictCursor)


def get_cursor():
    """Normal imleç döndür"""
    return mysql.connection.cursor()


def commit_db():
    """Değişiklikleri kaydet"""
    try:
        mysql.connection.commit()
    except Exception as e:
        # Bağlantı kapalıysa sessizce yoksay
        pass
