"""
İster Bullet API Controller'ı (Blueprint)
ister_bullet tablosu CRUD + sıralama işlemleri
"""
from flask import Blueprint, jsonify, request, session
from app.utils.database import mysql
from app.utils.auth import login_required
from app.utils.logging import record_log, LogType

bullet_api_bp = Blueprint('bullet_api', __name__, url_prefix='/api')


@bullet_api_bp.route('/ister_bullet/hepsi', methods=['GET'])
@login_required
def bullet_hepsi():
    """Tüm bullet'lar için BulletID ve NodeID listesini döner."""
    cur = mysql.connection.cursor(__import__('MySQLdb').cursors.DictCursor)
    cur.execute("SELECT BulletID, NodeID FROM ister_bullet")
    d = cur.fetchall()
    cur.close()
    return jsonify(d)


@bullet_api_bp.route('/ister_bullet/<int:node_id>', methods=['GET'])
@login_required
def bullet_listesi(node_id):
    """Belirli bir node'a ait bullet'ları sırayla döner."""
    cur = mysql.connection.cursor(__import__('MySQLdb').cursors.DictCursor)
    cur.execute(
        "SELECT * FROM ister_bullet WHERE NodeID=%s ORDER BY SiraNo, BulletID",
        (node_id,)
    )
    d = cur.fetchall()
    cur.close()
    return jsonify(d)


@bullet_api_bp.route('/ister_bullet', methods=['POST'])
@login_required
def bullet_ekle():
    """
    Yeni bullet ekler, sona yerleştirir.
    Body: { NodeID, Icerik }
    """
    d = request.json
    cur = mysql.connection.cursor(__import__('MySQLdb').cursors.DictCursor)
    cur.execute(
        "SELECT COALESCE(MAX(SiraNo), 0) + 1 AS sira FROM ister_bullet WHERE NodeID=%s",
        (d['NodeID'],)
    )
    sira = cur.fetchone()['sira']
    cur.execute(
        "INSERT INTO ister_bullet (NodeID, SiraNo, Icerik, OlusturanID) VALUES (%s, %s, %s, %s)",
        (d['NodeID'], sira, d['Icerik'], session['kullanici_id'])
    )
    mysql.connection.commit()
    bid = cur.lastrowid
    cur.close()
    record_log('ister_bullet', bid, 'Bullet', '-', d['Icerik'], LogType.CREATE.value)
    return jsonify({'BulletID': bid, 'SiraNo': sira})


@bullet_api_bp.route('/ister_bullet/<int:bid>', methods=['PUT'])
@login_required
def bullet_guncelle(bid):
    """
    Bullet içeriğini günceller.
    Body: { Icerik }
    """
    d = request.json
    cur = mysql.connection.cursor(__import__('MySQLdb').cursors.DictCursor)
    cur.execute("SELECT Icerik FROM ister_bullet WHERE BulletID=%s", (bid,))
    row = cur.fetchone()
    if not row:
        cur.close()
        return jsonify({'hata': 'Bullet bulunamadı.'}), 404
    eski_icerik = row['Icerik']
    record_log('ister_bullet', bid, 'Bullet', eski_icerik, d['Icerik'], LogType.UPDATE.value)
    cur.execute("UPDATE ister_bullet SET Icerik=%s WHERE BulletID=%s", (d['Icerik'], bid))
    mysql.connection.commit()
    cur.close()
    return jsonify({'ok': True})


@bullet_api_bp.route('/ister_bullet/<int:bid>', methods=['DELETE'])
@login_required
def bullet_sil(bid):
    """Bullet'ı siler."""
    cur = mysql.connection.cursor(__import__('MySQLdb').cursors.DictCursor)
    cur.execute("SELECT Icerik FROM ister_bullet WHERE BulletID=%s", (bid,))
    row = cur.fetchone()
    if not row:
        cur.close()
        return jsonify({'hata': 'Bullet bulunamadı.'}), 404
    record_log('ister_bullet', bid, 'Bullet', row['Icerik'], '-', LogType.DELETE.value)
    cur.execute("DELETE FROM ister_bullet WHERE BulletID=%s", (bid,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'ok': True})


@bullet_api_bp.route('/ister_bullet/siralama', methods=['POST'])
@login_required
def bullet_siralama():
    """
    Bullet sırasını değiştirir.
    Body: { BulletID, Yon: 'yukari' | 'asagi' }
    """
    d = request.json
    cur = mysql.connection.cursor(__import__('MySQLdb').cursors.DictCursor)
    cur.execute("SELECT NodeID, SiraNo FROM ister_bullet WHERE BulletID=%s", (d['BulletID'],))
    b = cur.fetchone()
    if not b:
        cur.close()
        return jsonify({'ok': True})

    yon = d.get('Yon', 'asagi')
    cur.execute(
        "SELECT BulletID, SiraNo FROM ister_bullet WHERE NodeID=%s ORDER BY SiraNo, BulletID",
        (b['NodeID'],)
    )
    tum = cur.fetchall()
    idx = next((i for i, x in enumerate(tum) if x['BulletID'] == d['BulletID']), -1)
    hedef = idx - 1 if yon == 'yukari' else idx + 1

    if 0 <= hedef < len(tum):
        cur2 = mysql.connection.cursor()
        cur2.execute(
            "UPDATE ister_bullet SET SiraNo=%s WHERE BulletID=%s",
            (tum[hedef]['SiraNo'], d['BulletID'])
        )
        cur2.execute(
            "UPDATE ister_bullet SET SiraNo=%s WHERE BulletID=%s",
            (tum[idx]['SiraNo'], tum[hedef]['BulletID'])
        )
        mysql.connection.commit()
        cur2.close()

    cur.close()
    return jsonify({'ok': True})
