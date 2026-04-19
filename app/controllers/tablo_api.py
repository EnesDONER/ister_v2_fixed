"""
İster Tablo API Controller'ı (Blueprint)
Kutucuk içi tablo (ister_tablo) CRUD işlemleri
"""
import json as json_mod
from flask import Blueprint, jsonify, request, session
from app.utils.database import mysql
from app.utils.auth import login_required
from app.utils.logging import record_log, LogType

tablo_api_bp = Blueprint('tablo_api', __name__, url_prefix='/api')


@tablo_api_bp.route('/ister_tablo/hepsi', methods=['GET'])
@login_required
def ister_tablo_hepsi():
    """Tüm tablolar için TabloID ve NodeID listesini döner."""
    cur = mysql.connection.cursor(__import__('MySQLdb').cursors.DictCursor)
    cur.execute("SELECT TabloID, NodeID FROM ister_tablo")
    d = cur.fetchall()
    cur.close()
    return jsonify(d)


@tablo_api_bp.route('/ister_tablo/<int:node_id>', methods=['GET'])
@login_required
def ister_tablo_listesi(node_id):
    """Belirli bir node'a ait tabloları döner."""
    cur = mysql.connection.cursor(__import__('MySQLdb').cursors.DictCursor)
    cur.execute("SELECT * FROM ister_tablo WHERE NodeID=%s ORDER BY TabloID", (node_id,))
    d = cur.fetchall()
    # JSON string alanları parse et
    for row in d:
        for field in ('SutunBasliklari', 'Satirlar'):
            if isinstance(row.get(field), str):
                try:
                    row[field] = json_mod.loads(row[field])
                except (ValueError, TypeError):
                    pass
    cur.close()
    return jsonify(d)


@tablo_api_bp.route('/ister_tablo', methods=['POST'])
@login_required
def ister_tablo_ekle():
    """
    Yeni tablo ekler.
    Body: { NodeID, TabloAdi, SutunBasliklari: [], Satirlar: [] }
    """
    d = request.json
    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO ister_tablo (NodeID, TabloAdi, SutunBasliklari, Satirlar, OlusturanID) VALUES (%s, %s, %s, %s, %s)",
        (
            d['NodeID'],
            d.get('TabloAdi', ''),
            json_mod.dumps(d.get('SutunBasliklari', [])),
            json_mod.dumps(d.get('Satirlar', [])),
            session['kullanici_id'],
        )
    )
    mysql.connection.commit()
    nid = cur.lastrowid
    cur.close()
    record_log('ister_tablo', nid, 'Tablo', '-', d.get('TabloAdi', ''), LogType.CREATE.value)
    return jsonify({'TabloID': nid})


@tablo_api_bp.route('/ister_tablo/<int:tid>', methods=['PUT'])
@login_required
def ister_tablo_guncelle(tid):
    """
    Tabloyu günceller.
    Body: { TabloAdi, SutunBasliklari: [], Satirlar: [] }
    """
    d = request.json
    cur = mysql.connection.cursor()
    cur.execute("SELECT TabloAdi, Satirlar FROM ister_tablo WHERE TabloID=%s", (tid,))
    row = cur.fetchone()
    eski_ad     = row[0] if row else '-'
    eski_satirlar = row[1] if row else '-'

    cur.execute(
        "UPDATE ister_tablo SET TabloAdi=%s, SutunBasliklari=%s, Satirlar=%s WHERE TabloID=%s",
        (
            d.get('TabloAdi', ''),
            json_mod.dumps(d.get('SutunBasliklari', [])),
            json_mod.dumps(d.get('Satirlar', [])),
            tid,
        )
    )
    mysql.connection.commit()
    cur.close()

    yeni_ad = d.get('TabloAdi', '')
    if yeni_ad:
        record_log('ister_tablo', tid, 'Tablo Adı', eski_ad, yeni_ad, LogType.UPDATE.value)
    else:
        record_log(
            'ister_tablo', tid, 'Tablo Satır Sütun',
            eski_satirlar, d.get('Satirlar', []),
            LogType.UPDATE.value
        )
    return jsonify({'ok': True})


@tablo_api_bp.route('/ister_tablo/<int:tid>', methods=['DELETE'])
@login_required
def ister_tablo_sil(tid):
    """Tabloyu siler."""
    cur = mysql.connection.cursor()
    cur.execute("SELECT TabloAdi FROM ister_tablo WHERE TabloID=%s", (tid,))
    row = cur.fetchone()
    tablo_adi = row[0] if row else '-'
    cur.execute("DELETE FROM ister_tablo WHERE TabloID=%s", (tid,))
    mysql.connection.commit()
    cur.close()
    record_log('ister_tablo', tid, 'Tablo', tablo_adi, '-', LogType.DELETE.value)
    return jsonify({'ok': True})
