from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

DB = 'farm_game.db'

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')  # 启用外键支持
    return conn

@app.route('/')
def index():
    conn = get_db()
    players = conn.execute('SELECT * FROM Player').fetchall()
    items = conn.execute('SELECT * FROM Item').fetchall()
    plants = conn.execute('SELECT * FROM Plant').fetchall()
    orders = conn.execute('SELECT * FROM VillagerOrder').fetchall()
    villagers = conn.execute('SELECT * FROM Villager').fetchall()
    inventory = conn.execute('SELECT * FROM Inventory').fetchall()
    shop_items = conn.execute('SELECT * FROM ShopItem').fetchall()
    plots = conn.execute('SELECT * FROM Plot').fetchall()
    conn.close()
    return render_template(
        'index.html',
        players=players,
        items=items,
        plants=plants,
        orders=orders,
        villagers=villagers,
        inventory=inventory,
        shop_items=shop_items,
        plots=plots
    )

@app.route('/add_player', methods=['POST'])
def add_player():
    gold = int(request.form['gold'])
    conn = get_db()
    conn.execute('INSERT INTO Player (CurrentGold) VALUES (?)', (gold,))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/add_item', methods=['POST'])
def add_item():
    name = request.form['item_name']
    category = request.form['category']
    desc = request.form['description']
    conn = get_db()
    conn.execute('INSERT INTO Item (ItemName, Category, Description) VALUES (?, ?, ?)', (name, category, desc))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/add_plant', methods=['POST'])
def add_plant():
    data = (
        request.form['plant_name'],
        int(request.form['growth_time']),
        int(request.form['water_effect']),
        int(request.form['max_water']),
        int(request.form['seed_price']),
        int(request.form['sell_price']),
        int(request.form['yield'])
    )
    conn = get_db()
    conn.execute('''INSERT INTO Plant 
                    (PlantName, BaseGrowthTime, WaterEffectPerTime, MaxWaterTimes, SeedPrice, SellPrice, HarvestYield)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''', data)
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/add_order', methods=['POST'])
def add_order():
    villager_id = int(request.form['villager_id'])
    item_id = int(request.form['item_id'])
    quantity = int(request.form['quantity'])
    reward = int(request.form['reward'])
    affection = int(request.form['affection'])

    conn = get_db()
    conn.execute('''
        INSERT INTO VillagerOrder 
        (VillagerID, RequiredItemID, RequiredQuantity, RewardGold, RewardAffection, Status) 
        VALUES (?, ?, ?, ?, ?, 'Available')
    ''', (villager_id, item_id, quantity, reward, affection))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/add_villager', methods=['POST'])
def add_villager():
    name = request.form['name']
    gender = request.form['gender']
    conn = get_db()
    conn.execute('INSERT INTO Villager (Name, Gender) VALUES (?, ?)', (name, gender))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/add_inventory', methods=['POST'])
def add_inventory():
    player_id = int(request.form['player_id'])
    item_id = int(request.form['item_id'])
    quantity = int(request.form['quantity'])
    conn = get_db()
    existing = conn.execute('SELECT Quantity FROM Inventory WHERE PlayerID=? AND ItemID=?', (player_id, item_id)).fetchone()
    if existing:
        conn.execute('UPDATE Inventory SET Quantity = Quantity + ? WHERE PlayerID=? AND ItemID=?',
                     (quantity, player_id, item_id))
    else:
        conn.execute('INSERT INTO Inventory (PlayerID, ItemID, Quantity) VALUES (?, ?, ?)',
                     (player_id, item_id, quantity))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/add_shop_item', methods=['POST'])
def add_shop_item():
    item_id = int(request.form['item_id'])
    sell_price = int(request.form['sell_price'])
    conn = get_db()
    existing = conn.execute('SELECT * FROM ShopItem WHERE ItemID=?', (item_id,)).fetchone()
    if existing:
        conn.execute('UPDATE ShopItem SET SellPrice=? WHERE ItemID=?', (sell_price, item_id))
    else:
        conn.execute('INSERT INTO ShopItem (ItemID, SellPrice) VALUES (?, ?)', (item_id, sell_price))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/delete_player/<int:pid>')
def delete_player(pid):
    conn = get_db()
    conn.execute('DELETE FROM Player WHERE PlayerID = ?', (pid,))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/delete_order/<int:oid>')
def delete_order(oid):
    conn = get_db()
    conn.execute('DELETE FROM VillagerOrder WHERE OrderID = ?', (oid,))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/complete_order/<int:oid>')
def complete_order(oid):
    conn = get_db()
    conn.execute('UPDATE VillagerOrder SET Status = ? WHERE OrderID = ?', ('Completed', oid))
    conn.commit()
    conn.close()
    return redirect('/')

from flask import jsonify

@app.route('/api/players')
def api_players():
    page = int(request.args.get('page', 1))
    keyword = request.args.get('q', '').strip()
    per_page = 5
    offset = (page - 1) * per_page

    conn = get_db()
    if keyword:
        players = conn.execute(
            'SELECT * FROM Player WHERE PlayerID LIKE ? LIMIT ? OFFSET ?', 
            (f'%{keyword}%', per_page, offset)
        ).fetchall()
        total = conn.execute(
            'SELECT COUNT(*) FROM Player WHERE PlayerID LIKE ?', 
            (f'%{keyword}%',)
        ).fetchone()[0]
    else:
        players = conn.execute(
            'SELECT * FROM Player LIMIT ? OFFSET ?', 
            (per_page, offset)
        ).fetchall()
        total = conn.execute('SELECT COUNT(*) FROM Player').fetchone()[0]

    conn.close()
    return jsonify({
        'players': [dict(p) for p in players],
        'total': total
    })

@app.route('/delete_item/<int:id>')
def delete_item(id):
    conn = get_db()
    conn.execute('DELETE FROM Item WHERE ItemID = ?', (id,))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/delete_plant/<int:id>')
def delete_plant(id):
    conn = get_db()
    conn.execute('DELETE FROM Plant WHERE PlantID = ?', (id,))
    conn.commit()
    conn.close()
    return '', 204
@app.route('/delete_inventory/<string:key>')

def delete_inventory(key):
    player_id, item_id = map(int, key.split('_'))
    conn = get_db()
    conn.execute('DELETE FROM Inventory WHERE PlayerID = ? AND ItemID = ?', (player_id, item_id))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/delete_shopitem/<int:id>')
def delete_shopitem(id):
    conn = get_db()
    conn.execute('DELETE FROM ShopItem WHERE ItemID = ?', (id,))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/delete_villager/<int:id>')
def delete_villager(id):
    conn = get_db()
    conn.execute('DELETE FROM Villager WHERE VillagerID = ?', (id,))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/delete_plot/<int:id>')
def delete_plot(id):
    conn = get_db()
    conn.execute('DELETE FROM Plot WHERE PlotID = ?', (id,))
    conn.commit()
    conn.close()
    return '', 204

from flask import jsonify, request

@app.route('/update_player/<int:pid>', methods=['POST'])
def update_player(pid):
    data = request.get_json()
    conn = get_db()
    conn.execute('UPDATE Player SET CurrentGold=? WHERE PlayerID=?', (data['gold'], pid))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/update_item/<int:id>', methods=['POST'])
def update_item(id):
    data = request.get_json()
    conn = get_db()
    conn.execute('UPDATE Item SET ItemName=?, Category=?, Description=? WHERE ItemID=?',
                (data['ItemName'], data['Category'], data['Description'], id))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/update_plant/<int:id>', methods=['POST'])
def update_plant(id):
    data = request.get_json()
    conn = get_db()
    conn.execute('''
        UPDATE Plant SET
            PlantName=?, BaseGrowthTime=?, WaterEffectPerTime=?, MaxWaterTimes=?,
            SeedPrice=?, SellPrice=?, HarvestYield=?
        WHERE PlantID=?
    ''', (
        data['PlantName'], int(data['BaseGrowthTime']), int(data['WaterEffectPerTime']),
        int(data['MaxWaterTimes']), int(data['SeedPrice']), int(data['SellPrice']),
        int(data['HarvestYield']), id
    ))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/update_order/<int:id>', methods=['POST'])
def update_order(id):
    data = request.get_json()
    conn = get_db()
    conn.execute('''
        UPDATE VillagerOrder SET
            VillagerID=?, RequiredItemID=?, RequiredQuantity=?,
            RewardGold=?, RewardAffection=?, Status=?
        WHERE OrderID=?
    ''', (
        data['VillagerID'], data['RequiredItemID'], data['RequiredQuantity'],
        data['RewardGold'], data['RewardAffection'], data['Status'], id
    ))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/update_inventory/<string:key>', methods=['POST'])
def update_inventory(key):
    player_id, item_id = map(int, key.split('_'))
    data = request.get_json()
    conn = get_db()
    conn.execute('UPDATE Inventory SET Quantity=? WHERE PlayerID=? AND ItemID=?',
                (int(data['Quantity']), player_id, item_id))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/update_shopitem/<int:id>', methods=['POST'])
def update_shopitem(id):
    data = request.get_json()
    conn = get_db()
    conn.execute('UPDATE ShopItem SET SellPrice=? WHERE ItemID=?', (int(data['SellPrice']), id))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/update_villager/<int:id>', methods=['POST'])
def update_villager(id):
    data = request.get_json()
    conn = get_db()
    conn.execute('UPDATE Villager SET Name=?, Gender=? WHERE VillagerID=?',
                (data['Name'], data['Gender'], id))
    conn.commit()
    conn.close()
    return '', 204

@app.route('/update_plot/<int:id>', methods=['POST'])
def update_plot(id):
    data = request.get_json()
    conn = get_db()
    conn.execute('UPDATE Plot SET PlayerID=?, Status=?, PlantedPlantID=? WHERE PlotID=?',
                (data['PlayerID'], data['Status'], data['PlantedPlantID'], id))
    conn.commit()
    conn.close()
    return '', 204


import os
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)


