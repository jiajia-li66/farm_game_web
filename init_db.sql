-- 用户表（用于注册登录）
CREATE TABLE IF NOT EXISTS User (
    UserID INTEGER PRIMARY KEY AUTOINCREMENT,
    Username TEXT UNIQUE NOT NULL,
    Password TEXT NOT NULL,
    Role TEXT CHECK(Role IN ('player', 'admin')) NOT NULL DEFAULT 'player'
);

-- 玩家表（与User一对一绑定）
CREATE TABLE IF NOT EXISTS Player (
    PlayerID INTEGER PRIMARY KEY AUTOINCREMENT,
    CurrentGold INTEGER NOT NULL DEFAULT 0,
    UserID INTEGER UNIQUE,
    FOREIGN KEY (UserID) REFERENCES User(UserID)
);

-- 物品表
CREATE TABLE IF NOT EXISTS Item (
    ItemID INTEGER PRIMARY KEY AUTOINCREMENT,
    ItemName TEXT NOT NULL UNIQUE,
    Category TEXT NOT NULL,
    Description TEXT
);

-- 植物表
CREATE TABLE IF NOT EXISTS Plant (
    PlantID INTEGER PRIMARY KEY AUTOINCREMENT,
    PlantName TEXT NOT NULL UNIQUE,
    BaseGrowthTime INTEGER NOT NULL,
    WaterEffectPerTime INTEGER NOT NULL,
    MaxWaterTimes INTEGER NOT NULL,
    SeedPrice INTEGER NOT NULL,
    SellPrice INTEGER NOT NULL,
    HarvestYield INTEGER NOT NULL DEFAULT 1
);

-- 土地表
CREATE TABLE IF NOT EXISTS Plot (
    PlotID INTEGER PRIMARY KEY AUTOINCREMENT,           -- 地块ID
    PlayerID INTEGER NOT NULL,                          -- 所属玩家
    Status TEXT NOT NULL DEFAULT 'Empty',               -- 状态：Empty/Growing/Ready
    PlantedPlantID INTEGER,                             -- 当前种植的作物（对应 Plant 表）
    CurrentGrowthTimeLeft INTEGER,                      -- 剩余生长时间（由 BaseGrowthTime 决定）
    TimesWatered INTEGER NOT NULL DEFAULT 0,            -- 浇水次数
    FOREIGN KEY (PlayerID) REFERENCES Player(PlayerID),
    FOREIGN KEY (PlantedPlantID) REFERENCES Plant(PlantID)
);


-- 仓库表（玩家 × 物品）
CREATE TABLE IF NOT EXISTS Inventory (
    PlayerID INTEGER NOT NULL,
    ItemID INTEGER NOT NULL,
    Quantity INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (PlayerID, ItemID),
    FOREIGN KEY (PlayerID) REFERENCES Player(PlayerID),
    FOREIGN KEY (ItemID) REFERENCES Item(ItemID)
);

-- 村民表
CREATE TABLE IF NOT EXISTS Villager (
    VillagerID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL,
    Gender TEXT NOT NULL,
    Description TEXT
);

-- 好感度表
CREATE TABLE IF NOT EXISTS Affection (
    PlayerID INTEGER NOT NULL,
    VillagerID INTEGER NOT NULL,
    AffectionLevel INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (PlayerID, VillagerID),
    FOREIGN KEY (PlayerID) REFERENCES Player(PlayerID),
    FOREIGN KEY (VillagerID) REFERENCES Villager(VillagerID)
);

-- 村民订单表（共用）
CREATE TABLE IF NOT EXISTS VillagerOrder (
    OrderID INTEGER PRIMARY KEY AUTOINCREMENT,
    VillagerID INTEGER NOT NULL,
    RequiredItemID INTEGER NOT NULL,
    RequiredQuantity INTEGER NOT NULL DEFAULT 1,
    RewardGold INTEGER NOT NULL,
    RewardAffection INTEGER NOT NULL DEFAULT 0,
    Status TEXT NOT NULL DEFAULT 'Available',
    PostedTime TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ExpiryTime TEXT,
    FOREIGN KEY (VillagerID) REFERENCES Villager(VillagerID),
    FOREIGN KEY (RequiredItemID) REFERENCES Item(ItemID)
);


-- 金币交易记录表
CREATE TABLE IF NOT EXISTS GoldTransaction (
    TransactionID INTEGER PRIMARY KEY AUTOINCREMENT,
    PlayerID INTEGER NOT NULL,
    Timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Type TEXT NOT NULL,  -- Income / Expense
    Amount INTEGER NOT NULL,
    SourceReference TEXT NOT NULL,
    FOREIGN KEY (PlayerID) REFERENCES Player(PlayerID)
);

-- 商店中可购买物品
CREATE TABLE IF NOT EXISTS ShopItem (
    ItemID INTEGER PRIMARY KEY,
    SellPrice INTEGER NOT NULL,
    FOREIGN KEY (ItemID) REFERENCES Item(ItemID)
);

INSERT INTO Item (ItemName, Category, Description) VALUES 
('萝卜种子', '种子', '用于种植萝卜'),
('胡萝卜', '作物', '成熟后的萝卜'),
('水滴', '材料', '用于浇水');

INSERT INTO Plant (PlantName, BaseGrowthTime, WaterEffectPerTime, MaxWaterTimes, SeedPrice, SellPrice, HarvestYield) VALUES
('萝卜', 60, 10, 3, 5, 15, 1),
('胡萝卜', 90, 15, 2, 8, 20, 1),
('小麦', 70, 13, 3, 6, 18, 1);

-- 添加村民
INSERT INTO Villager (Name, Gender, Description) VALUES
('小芳', '女', '热情的村花，希望有人帮她收集萝卜'),
('老张', '男', '经验丰富的农民，正在寻找小麦');


-- 添加村民订单（物品ID 你要根据实际 Item 表中的 ID 对应）
INSERT INTO VillagerOrder (VillagerID, RequiredItemID, RequiredQuantity, RewardGold, RewardAffection) VALUES
(1, 1, 5, 50, 5),   -- 小芳要5个萝卜，给50金币+5好感
(2, 2, 3, 70, 8);   -- 老张要3个小麦，给70金币+8好感


-- 假设萝卜种子、水滴可以被玩家购买
INSERT INTO ShopItem (ItemID, SellPrice)
SELECT ItemID, 5 FROM Item WHERE ItemName = '萝卜种子'
UNION ALL
SELECT ItemID, 2 FROM Item WHERE ItemName = '水滴';

INSERT INTO User (Username, Password, Role) VALUES 
('admin', 'admin123', 'admin'),
('player1', '123456', 'player');
