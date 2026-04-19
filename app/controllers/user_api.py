"""
Kullanıcı API Controller'ı (Blueprint)
"""
from flask import Blueprint, jsonify, request, session
from app.utils.database import mysql
from app.utils.auth import login_required
from app.utils.logging import record_log, LogType

user_api_bp = Blueprint('user_api', __name__, url_prefix='/api')


@user_api_bp.route('/kullanici', methods=['GET'])
@login_required
def kullanici_listesi():
    cur = mysql.connection.cursor(__import__('MySQLdb').cursors.DictCursor)
    cur.execute("SELECT KullaniciID, KullaniciAdi, AdSoyad, AktifMi FROM kullanici ORDER BY KullaniciAdi")
    d = cur.fetchall()
    cur.close()
    return jsonify(d)


@user_api_bp.route('/kullanici', methods=['POST'])
@login_required
def kullanici_ekle():
    d = request.json
    cur = mysql.connection.cursor(__import__('MySQLdb').cursors.DictCursor)
    cur.execute("SELECT KullaniciID FROM kullanici WHERE KullaniciAdi=%s", (d['KullaniciAdi'],))
    if cur.fetchone():
        cur.close()
        return jsonify({'hata': 'Bu kullanıcı adı mevcut.'}), 400
    cur.execute(
        "INSERT INTO kullanici (KullaniciAdi, Sifre, AdSoyad, AktifMi) VALUES (%s, %s, %s, %s)",
        (d['KullaniciAdi'], d['Sifre'], d.get('AdSoyad', ''), d.get('AktifMi', 1))
    )
    mysql.connection.commit()
    nid = cur.lastrowid
    cur.close()
    record_log('kullanici', nid, 'Kullanıcılar', '-', d.get('KullaniciAdi', ''), LogType.CREATE.value)
    return jsonify({'KullaniciID': nid})


@user_api_bp.route('/kullanici/<int:uid>', methods=['PUT'])
@login_required
def kullanici_guncelle(uid):
    d = request.json
    cur = mysql.connection.cursor()
    cur.execute("SELECT KullaniciAdi FROM kullanici WHERE KullaniciID=%s", (uid,))
    eski = cur.fetchone()
    eski_kadi = eski[0] if eski else ''
    if d.get('Sifre'):
        cur.execute(
            "UPDATE kullanici SET KullaniciAdi=%s, AdSoyad=%s, AktifMi=%s, Sifre=%s WHERE KullaniciID=%s",
            (d['KullaniciAdi'], d.get('AdSoyad', ''), d.get('AktifMi', 1), d['Sifre'], uid)
        )
    else:
        cur.execute(
            "UPDATE kullanici SET KullaniciAdi=%s, AdSoyad=%s, AktifMi=%s WHERE KullaniciID=%s",
            (d['KullaniciAdi'], d.get('AdSoyad', ''), d.get('AktifMi', 1), uid)
        )
    mysql.connection.commit()
    cur.close()
    record_log('kullanici', uid, 'Kullanıcılar', eski_kadi, d.get('KullaniciAdi', ''), LogType.UPDATE.value)
    return jsonify({'ok': True})


@user_api_bp.route('/kullanici/<int:uid>', methods=['DELETE'])
@login_required
def kullanici_sil(uid):
    if uid == session.get('kullanici_id'):
        return jsonify({'hata': 'Kendi hesabınızı silemezsiniz.'}), 400
    cur = mysql.connection.cursor()
    record_log('kullanici', uid, 'Kullanıcılar', 'Silindi', '-', LogType.DELETE.value)
    cur.execute("DELETE FROM kullanici WHERE KullaniciID=%s", (uid,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'ok': True})
