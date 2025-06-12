# app.py
from flask import Flask, render_template, redirect, url_for, request, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'secret-key'  # 用于 session 加密

DB_PATH = 'farm_game.db'

def get_current_player():
    if 'user_id' not in session:
        return None
    conn = get_db()
    user_id = session['user_id']
    player = conn.execute("SELECT * FROM Player WHERE UserID = ?", (user_id,)).fetchone()
    conn.close()
    return player

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('player_dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db()
        cur = conn.cursor()

        # 检查用户名是否已存在
        cur.execute("SELECT * FROM User WHERE Username = ?", (username,))
        if cur.fetchone():
            flash('用户名已存在！')
            return redirect(url_for('register'))

        # 插入新用户
        hashed_pw = generate_password_hash(password)
        cur.execute("INSERT INTO User (Username, Password, Role) VALUES (?, ?, 'player')", (username, hashed_pw))
        user_id = cur.lastrowid

        # 创建玩家并初始化金币
        cur.execute("INSERT INTO Player (CurrentGold, UserID) VALUES (?, ?)", (100, user_id))
        player_id = cur.lastrowid

        # 给新玩家添加一块空地
        cur.execute("INSERT INTO Plot (PlayerID, Status) VALUES (?, 'Empty')", (player_id,))

        # 添加种子库存：假设有种子物品 ID 是 1 和 2
        init_seeds = [(1, 3), (3, 2)]  # [(ItemID, 数量)]
        for item_id, quantity in init_seeds:
            cur.execute("INSERT INTO Inventory (PlayerID, ItemID, Quantity) VALUES (?, ?, ?)", (player_id, item_id, quantity))

        conn.commit()
        conn.close()

        flash('注册成功，已为你分配：💰100金币、🧺种子、🏡一块土地，请登录游戏查看！')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
        cursor = conn.cursor()
        user = cursor.execute("SELECT * FROM User WHERE Username=? AND Password=?", (username, password)).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['UserID']
            session['username'] = user['Username']
            session['role'] = user['Role']
            flash('登录成功！', 'success')
            if user['Role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('player_dashboard'))
        else:
            flash('用户名或密码错误', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('已退出登录', 'info')
    return redirect(url_for('login'))



@app.route('/player/dashboard')
def player_dashboard():
    if session.get('role') != 'player':
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT PlayerID, CurrentGold FROM Player WHERE UserID = ?", (user_id,))
    player = cur.fetchone()

    cur.execute("""
        SELECT i.ItemName, inv.Quantity
        FROM Inventory inv
        JOIN Item i ON inv.ItemID = i.ItemID
        WHERE inv.PlayerID = ?
    """, (player['PlayerID'],))
    inventory = cur.fetchall()

    cur.execute("SELECT * FROM Plot WHERE PlayerID = ?", (player['PlayerID'],))
    plots = cur.fetchall()

    conn.close()
    return render_template('player_dashboard.html', player=player, inventory=inventory, plots=plots)

@app.route('/shop', methods=['GET'])
def shop():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor()

    # 获取玩家信息
    cur.execute("SELECT PlayerID, CurrentGold FROM Player WHERE UserID = ?", (session['user_id'],))
    player = cur.fetchone()

    # 获取商店可售物品
    cur.execute("""
        SELECT si.ItemID, i.ItemName, si.SellPrice
        FROM ShopItem si
        JOIN Item i ON si.ItemID = i.ItemID
    """)
    items = cur.fetchall()

    conn.close()
    return render_template('shop.html', player=player, items=items)


@app.route('/shop/buy/<int:item_id>', methods=['POST'])
def shop_buy(item_id):
    if session.get('role') != 'player':
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT PlayerID, CurrentGold FROM Player WHERE UserID = ?", (session['user_id'],))
    player = cur.fetchone()

    cur.execute("SELECT SellPrice FROM ShopItem WHERE ItemID = ?", (item_id,))
    item = cur.fetchone()
    if not item:
        flash('商品不存在')
        return redirect(url_for('shop'))

    if player['CurrentGold'] < item['SellPrice']:
        flash('金币不足')
        return redirect(url_for('shop'))

    new_gold = player['CurrentGold'] - item['SellPrice']
    cur.execute("UPDATE Player SET CurrentGold = ? WHERE PlayerID = ?", (new_gold, player['PlayerID']))

    cur.execute("SELECT Quantity FROM Inventory WHERE PlayerID = ? AND ItemID = ?", (player['PlayerID'], item_id))
    inv = cur.fetchone()
    if inv:
        cur.execute("UPDATE Inventory SET Quantity = Quantity + 1 WHERE PlayerID = ? AND ItemID = ?", (player['PlayerID'], item_id))
    else:
        cur.execute("INSERT INTO Inventory (PlayerID, ItemID, Quantity) VALUES (?, ?, 1)", (player['PlayerID'], item_id))

    conn.commit()
    conn.close()
    flash('购买成功')
    return redirect(url_for('shop'))

@app.route('/plant', methods=['GET', 'POST'])
def plant():
    if session.get('role') != 'player':
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT PlayerID FROM Player WHERE UserID = ?", (user_id,))
    player = cur.fetchone()

    if request.method == 'POST':
        plot_id = request.form['plot_id']
        plant_id = request.form['plant_id']

        cur.execute("SELECT Quantity FROM Inventory WHERE PlayerID = ? AND ItemID = ?", (player['PlayerID'], plant_id))
        seed = cur.fetchone()
        if not seed or seed['Quantity'] < 1:
            flash('你没有这个种子的库存')
            return redirect(url_for('plant'))

        cur.execute("SELECT BaseGrowthTime FROM Plant WHERE PlantID = ?", (plant_id,))
        base_time = cur.fetchone()['BaseGrowthTime']

        cur.execute("UPDATE Plot SET PlantedPlantID = ?, Status = 'Growing', CurrentGrowthTimeLeft = ?, TimesWatered = 0 WHERE PlotID = ? AND PlayerID = ?", (plant_id, base_time, plot_id, player['PlayerID']))
        cur.execute("UPDATE Inventory SET Quantity = Quantity - 1 WHERE PlayerID = ? AND ItemID = ?", (player['PlayerID'], plant_id))
        conn.commit()
        conn.close()
        flash('种植成功')
        return redirect(url_for('player_dashboard'))

    cur.execute("SELECT * FROM Plot WHERE PlayerID = ? AND Status = 'Empty'", (player['PlayerID'],))
    empty_plots = cur.fetchall()

    cur.execute("""
        SELECT p.PlantID, p.PlantName, i.ItemID, i.ItemName AS SeedName, inv.Quantity
        FROM Plant p
        JOIN Item i ON p.PlantName = REPLACE(i.ItemName, '种子', '')
        JOIN Inventory inv ON inv.ItemID = i.ItemID AND inv.PlayerID = ?
        WHERE inv.Quantity > 0
    """, (player['PlayerID'],))
    seeds = cur.fetchall()

    conn.close()
    return render_template('plant.html', plots=empty_plots, seeds=seeds)

@app.route('/water/<int:plot_id>', methods=['POST'])
def water(plot_id):
    if session.get('role') != 'player':
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT PlayerID FROM Player WHERE UserID = ?", (user_id,))
    player = cur.fetchone()

    cur.execute("SELECT PlantedPlantID, CurrentGrowthTimeLeft, TimesWatered FROM Plot WHERE PlotID = ? AND PlayerID = ? AND Status = 'Growing'", (plot_id, player['PlayerID']))
    plot = cur.fetchone()
    if not plot:
        flash('无法浇水：该土地不可操作')
        return redirect(url_for('player_dashboard'))

    cur.execute("SELECT MaxWaterTimes, WaterEffectPerTime FROM Plant WHERE PlantID = ?", (plot['PlantedPlantID'],))
    plant_info = cur.fetchone()

    if plot['TimesWatered'] >= plant_info['MaxWaterTimes']:
        flash('已达最大浇水次数')
        return redirect(url_for('player_dashboard'))

    cur.execute("SELECT Quantity FROM Inventory WHERE PlayerID = ? AND ItemID = (SELECT ItemID FROM Item WHERE ItemName = '水滴')", (player['PlayerID'],))
    water = cur.fetchone()
    if not water or water['Quantity'] < 1:
        flash('没有足够的水滴')
        return redirect(url_for('player_dashboard'))

    new_time = max(0, plot['CurrentGrowthTimeLeft'] - plant_info['WaterEffectPerTime'])
    cur.execute("""
        UPDATE Plot SET
            CurrentGrowthTimeLeft = ?,
            TimesWatered = TimesWatered + 1
        WHERE PlotID = ?
    """, (new_time, plot_id))

    cur.execute("UPDATE Inventory SET Quantity = Quantity - 1 WHERE PlayerID = ? AND ItemID = (SELECT ItemID FROM Item WHERE ItemName = '水滴')", (player['PlayerID'],))
    conn.commit()
    conn.close()

    flash('浇水成功')
    return redirect(url_for('player_dashboard'))

from flask import flash

@app.route('/harvest_all', methods=['GET', 'POST'])
def harvest():
    player = get_current_player()
    conn = get_db()
    cur = conn.cursor()

    # 查询所有可收获地块
    ready_plots = cur.execute("""
        SELECT * FROM Plot WHERE PlayerID = ? AND Status = 'Ready'
    """, (player['PlayerID'],)).fetchall()

    if not ready_plots:
        flash("当前没有可收获的作物！", "warning")
        return redirect(url_for('player_dashboard'))

    for plot in ready_plots:
        # 查作物信息
        plant = cur.execute("SELECT * FROM Plant WHERE PlantID = ?", (plot['PlantedPlantID'],)).fetchone()

        # 找对应的 Item（比如“萝卜”）
        item = cur.execute("SELECT ItemID FROM Item WHERE ItemName = ?", (plant['PlantName'],)).fetchone()
        if not item:
            flash(f"作物 {plant['PlantName']} 无对应物品，跳过。", "danger")
            continue

        # 插入或更新 Inventory
        cur.execute("""
            INSERT INTO Inventory (PlayerID, ItemID, Quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(PlayerID, ItemID) DO UPDATE SET Quantity = Quantity + excluded.Quantity
        """, (player['PlayerID'], item['ItemID'], plant['HarvestYield']))

        # 清空地块
        cur.execute("""
            UPDATE Plot SET Status = 'Empty', PlantedPlantID = NULL,
                            CurrentGrowthTimeLeft = NULL, TimesWatered = 0
            WHERE PlotID = ?
        """, (plot['PlotID'],))

    conn.commit()
    conn.close()
    flash("作物已成功收获 ✅", "success")
    return redirect(url_for('player_dashboard'))




@app.route('/do_harvest/<int:plot_id>', methods=['GET', 'POST'])
def do_harvest(plot_id):
    if session.get('role') != 'player':
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor()

    # 找到当前玩家 ID
    cur.execute("SELECT PlayerID FROM Player WHERE UserID = ?", (session['user_id'],))
    player = cur.fetchone()

    # 查询该地块是否可收获
    cur.execute("""
        SELECT pl.SellPrice, pl.HarvestYield
        FROM Plot p
        JOIN Plant pl ON p.PlantedPlantID = pl.PlantID
        WHERE p.PlotID = ? AND p.PlayerID = ? AND p.Status = 'Ready'
    """, (plot_id, player['PlayerID']))
    plant_info = cur.fetchone()

    if not plant_info:
        flash("❌ 无法收获：该地块未成熟或不存在。")
        return redirect(url_for('player_dashboard'))

    # 收获逻辑：获得金币 + 清除地块
    total_gold = plant_info['SellPrice'] * plant_info['HarvestYield']
    cur.execute("UPDATE Player SET CurrentGold = CurrentGold + ? WHERE PlayerID = ?", (total_gold, player['PlayerID']))
    cur.execute("UPDATE Plot SET Status = 'Empty', PlantedPlantID = NULL, CurrentGrowthTimeLeft = NULL, TimesWatered = 0 WHERE PlotID = ?", (plot_id,))

    conn.commit()
    conn.close()

    flash(f"✅ 收获成功，获得金币 {total_gold}！")
    return redirect(url_for('player_dashboard'))

@app.route('/next_day', methods=['POST'])
def next_day():
    if session.get('role') != 'player':
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT PlayerID FROM Player WHERE UserID = ?", (session['user_id'],))
    player = cur.fetchone()

    # 所有生长中的地块减少成长时间
    cur.execute("""
        UPDATE Plot
        SET 
            CurrentGrowthTimeLeft = CASE 
                WHEN CurrentGrowthTimeLeft - 1 <= 0 THEN 0
                ELSE CurrentGrowthTimeLeft - 1
            END,
            Status = CASE 
                WHEN CurrentGrowthTimeLeft - 1 <= 0 THEN 'Ready'
                ELSE 'Growing'
            END
        WHERE PlayerID = ? AND Status = 'Growing'
    """, (player['PlayerID'],))

    conn.commit()
    conn.close()
    return redirect(url_for('player_dashboard'))


@app.route('/submit_order', methods=['POST'])
def submit_order():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    order_id = int(request.form['order_id'])

    conn = get_db()
    cur = conn.cursor()

    # 获取玩家 ID
    cur.execute("SELECT PlayerID FROM Player WHERE UserID = ?", (session['user_id'],))
    player = cur.fetchone()
    if not player:
        flash("未找到玩家。")
        return redirect(url_for('index'))

    player_id = player['PlayerID']

    # 获取订单详情
    cur.execute("""
        SELECT vo.RequiredItemID, vo.RequiredQuantity, vo.RewardGold, vo.RewardAffection,
               v.VillagerID
        FROM VillagerOrder vo
        JOIN Villager v ON vo.VillagerID = v.VillagerID
        WHERE vo.OrderID = ? AND vo.Status = 'Available'
    """, (order_id,))
    order = cur.fetchone()

    if not order:
        flash("订单无效或已完成。")
        return redirect(url_for('index'))

    # 检查背包是否足够
    cur.execute("""
        SELECT Quantity FROM Inventory
        WHERE PlayerID = ? AND ItemID = ?
    """, (player_id, order['RequiredItemID']))
    inv = cur.fetchone()

    if not inv or inv['Quantity'] < order['RequiredQuantity']:
        flash("仓库物品不足，无法完成订单。")
        return redirect(url_for('index'))

    # 减去物品、加金币、加好感、更新订单状态
    cur.execute("""
        UPDATE Inventory SET Quantity = Quantity - ?
        WHERE PlayerID = ? AND ItemID = ?
    """, (order['RequiredQuantity'], player_id, order['RequiredItemID']))

    cur.execute("""
        UPDATE Player SET CurrentGold = CurrentGold + ?
        WHERE PlayerID = ?
    """, (order['RewardGold'], player_id))

    cur.execute("""
        INSERT INTO Affection (PlayerID, VillagerID, AffectionLevel)
        VALUES (?, ?, ?)
        ON CONFLICT(PlayerID, VillagerID) DO UPDATE SET AffectionLevel = AffectionLevel + excluded.AffectionLevel
    """, (player_id, order['VillagerID'], order['RewardAffection']))

    cur.execute("""
        UPDATE VillagerOrder SET Status = 'Completed', PlayerID = ?
        WHERE OrderID = ?
    """, (player_id, order_id))

    # 记录收入
    cur.execute("""
        INSERT INTO GoldTransaction (PlayerID, Type, Amount, SourceReference)
        VALUES (?, 'Income', ?, '完成订单 {}')
    """.format(order_id), (player_id, order['RewardGold']))

    conn.commit()
    conn.close()
    flash("订单完成，奖励已发放！")
    return redirect(url_for('index'))

@app.route('/orders')
def view_orders():
    player = get_current_player()
    if not player:
        return redirect('/login')

    conn = get_db()
    orders = conn.execute("""
        SELECT vo.OrderID, v.VillagerName AS VillagerName, i.ItemName, vo.RequiredQuantity,
               vo.RewardGold, vo.RewardAffection, vo.Status
        FROM VillagerOrder vo
        JOIN Villager v ON vo.VillagerID = v.VillagerID
        JOIN Item i ON vo.RequiredItemID = i.ItemID
        WHERE vo.Status = 'Available'
    """).fetchall()
    conn.close()
    return render_template('orders.html', orders=orders, player=player)

@app.route('/orders/complete/<int:order_id>', methods=['POST'])
def complete_order(order_id):
    player = get_current_player()
    if not player:
        return redirect('/login')
    player_id = player['PlayerID']

    conn = get_db()
    # 查询订单详情
    order = conn.execute("""
        SELECT * FROM VillagerOrder WHERE OrderID = ? AND Status = 'Available'
    """, (order_id,)).fetchone()

    if not order:
        flash("订单不存在或已完成")
        return redirect('/orders')

    item_id = order['RequiredItemID']
    quantity = order['RequiredQuantity']
    reward_gold = order['RewardGold']
    reward_affection = order['RewardAffection']
    villager_id = order['VillagerID']

    # 检查背包是否足够
    inv = conn.execute("""
        SELECT Quantity FROM Inventory WHERE PlayerID = ? AND ItemID = ?
    """, (player_id, item_id)).fetchone()

    if not inv or inv['Quantity'] < quantity:
        flash("背包物品不足，无法完成订单")
        return redirect('/orders')

    # 扣除物品
    conn.execute("""
        UPDATE Inventory SET Quantity = Quantity - ?
        WHERE PlayerID = ? AND ItemID = ?
    """, (quantity, player_id, item_id))

    # 增加金币
    conn.execute("""
        UPDATE Player SET CurrentGold = CurrentGold + ?
        WHERE PlayerID = ?
    """, (reward_gold, player_id))

    # 增加好感度（若无记录先插入）
    conn.execute("""
        INSERT INTO Affection (PlayerID, VillagerID, AffectionLevel)
        VALUES (?, ?, ?)
        ON CONFLICT(PlayerID, VillagerID)
        DO UPDATE SET AffectionLevel = AffectionLevel + ?
    """, (player_id, villager_id, reward_affection, reward_affection))

    # 标记订单已完成
    conn.execute("""
        UPDATE VillagerOrder SET Status = 'Completed', PlayerID = ?
        WHERE OrderID = ?
    """, (player_id, order_id))

    conn.commit()
    conn.close()
    flash("订单完成，已获得奖励！")
    return redirect('/orders')


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if session.get('role') != 'admin':
        flash("权限不足")
        return redirect(url_for('login'))

    conn = get_db()
    # 删除关联的玩家、物品等应加级联（或前提处理）
    conn.execute("DELETE FROM User WHERE UserID = ?", (user_id,))
    conn.commit()
    conn.close()
    flash("用户已删除")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM User")
    users = cur.fetchall()

    cur.execute("SELECT * FROM Player")
    players = cur.fetchall()

    cur.execute("SELECT * FROM Plant")
    plants = cur.fetchall()

    cur.execute("SELECT * FROM Item")
    items = cur.fetchall()

    cur.execute("SELECT * FROM Villager")
    villagers = cur.fetchall()

    conn.close()
    return render_template('admin_dashboard.html',
                           users=users,
                           players=players,
                           plants=plants,
                           items=items,
                           villagers=villagers)


@app.route('/admin/manage_all', methods=['GET', 'POST'])
def admin_manage_all():
    conn = get_db()
    cur = conn.cursor()

    if request.method == 'POST':
        form_type = request.form.get('form_type')

        try:
            if form_type == 'plant':
                name = request.form['name']
                existing = cur.execute("SELECT 1 FROM Plant WHERE PlantName = ?", (name,)).fetchone()
                if existing:
                    flash('植物名称已存在，请更换名称', 'warning')
                else:
                    cur.execute("""
                        INSERT INTO Plant (PlantName, BaseGrowthTime, MaxWaterTimes, WaterEffectPerTime, HarvestYield, SellPrice)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        name,
                        request.form['growth'],
                        request.form['max_water'],
                        request.form['effect'],
                        request.form['yield'],
                        request.form['price']
                    ))
                    conn.commit()
                    flash('植物添加成功', 'success')

            elif form_type == 'item':
                item_name = request.form['item_name']
                existing = cur.execute("SELECT 1 FROM Item WHERE ItemName = ?", (item_name,)).fetchone()
                if existing:
                    flash('物品名称已存在', 'warning')
                else:
                    cur.execute("""
                        INSERT INTO Item (ItemName, ItemType, Description)
                        VALUES (?, ?, ?)
                    """, (
                        item_name,
                        request.form['item_type'],
                        request.form['item_desc']
                    ))
                    conn.commit()
                    flash('物品添加成功', 'success')

            elif form_type == 'villager':
                villager_name = request.form['villager_name']
                gender = request.form['villager_gender']
                description = request.form['villager_desc']
                
                existing = cur.execute("SELECT 1 FROM Villager WHERE VillagerName = ?", (villager_name,)).fetchone()
                if existing:
                    flash('村民姓名已存在', 'warning')
                else:
                    cur.execute("""
                        INSERT INTO Villager (VillagerName, Gender, Description)
                        VALUES (?, ?, ?)
                    """, (
                        villager_name,
                        gender,
                        description
                    ))
                    conn.commit()
                    flash('村民添加成功', 'success')

        except Exception as e:
            conn.rollback()
            flash(f'发生错误：{e}', 'danger')

    # 获取所有数据用于展示
    plants = cur.execute("SELECT * FROM Plant").fetchall()
    items = cur.execute("SELECT * FROM Item").fetchall()
    villagers = cur.execute("SELECT * FROM Villager").fetchall()
    conn.close()

    return render_template('admin_manage_all.html', plants=plants, items=items, villagers=villagers)


@app.route('/admin/delete_plant/<int:plant_id>', methods=['POST'])
def delete_plant(plant_id):
    conn = get_db()
    conn.execute("DELETE FROM Plant WHERE PlantID = ?", (plant_id,))
    conn.commit()
    conn.close()
    flash('植物已删除','success')
    return redirect(url_for('admin_manage_all'))

@app.route('/admin/delete_item/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    conn = get_db()
    conn.execute("DELETE FROM Item WHERE ItemID = ?", (item_id,))
    conn.commit()
    conn.close()
    flash('物品已删除','success')
    return redirect(url_for('admin_manage_all'))

@app.route('/admin/delete_villager/<int:villager_id>', methods=['POST'])
def delete_villager(villager_id):
    conn = get_db()
    conn.execute("DELETE FROM Villager WHERE VillagerID = ?", (villager_id,))
    conn.commit()
    conn.close()
    flash('村民已删除','success')
    return redirect(url_for('admin_manage_all'))


if __name__ == '__main__':
    app.run(debug=True)
