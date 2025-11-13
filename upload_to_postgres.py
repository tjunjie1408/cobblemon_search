import json
import os
import sys
import sqlalchemy
from sqlalchemy import create_engine, text

print("--- Render 部署脚本 (Postgres版) 启动 ---")

# 1. 从环境变量中读取数据库连接 URL
# Render 会自动提供这个 'DATABASE_URL'
# !! 注意：我们使用的是 'DATABASE_URL'，而不是 'INTERNAL_CONNECTION_URL' !!
# Render 的 build 过程可能无法访问 "Internal" URL
DATABASE_URL = os.environ.get('postgresql://cobblemon_db_user:xzNcuiu5XdVwo2MLQlbQEVnzetk9wb9b@dpg-d4apcrogjchc73f1nmp0-a.oregon-postgres.render.com/cobblemon_db')

if not DATABASE_URL:
    print("!! 错误: 未能在环境变量中找到 'DATABASE_URL' !!")
    print("请检查你的 Render Web Service > Environment 设置。")
    sys.exit(1) # 退出并导致 build 失败

JSON_FILE_PATH = 'all_spawns_processed_ENRICHED.json'
TABLE_NAME = 'spawns'

try:
    print(f"正在连接到 Postgres 数据库...")
    # 使用 SQLAlchemy 创建连接
    # Render 提供的 DATABASE_URL 可能是 postgres://...
    # SQLAlchemy 1.4+ 需要 postgresql://...
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        
    engine = create_engine(DATABASE_URL)

    print("正在加载 JSON 数据...")
    with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
        documents = json.load(f)
    print(f"成功加载 {len(documents)} 条规则。")

    # 2. 创建表 (如果已存在则先删除)
    # 我们将把整个 JSON 对象存储在 'data' 字段中 (使用 JSONB 类型)
    # 并为几个关键字段建立索引以加快搜索速度
    with engine.connect() as conn:
        print(f"正在创建或重置 '{TABLE_NAME}' 表...")
        conn.execute(text(f"DROP TABLE IF EXISTS {TABLE_NAME};"))
        conn.execute(text(f"""
            CREATE TABLE {TABLE_NAME} (
                id VARCHAR(255) PRIMARY KEY,
                pokemon_name VARCHAR(255),
                features VARCHAR(100)[],
                generation INT,
                bucket VARCHAR(50),
                level_min INT,
                data JSONB 
            );
        """))
        
        # 3. 插入数据
        print(f"正在插入 {len(documents)} 条数据... 这可能需要1-2分钟。")
        
        # 我们将分批次插入以提高效率
        batch_size = 500
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            insert_data = []
            for doc in batch:
                # 提取用于索引的字段
                species_name = doc.get('species', {}).get('name', doc.get('pokemon')).split(' ')[0]
                features_list = doc.get('features', [])
                generation = doc.get('species', {}).get('generation')
                
                insert_data.append({
                    'id': doc.get('id'),
                    'pokemon_name': species_name.lower(), # 转换为小写以便不区分大小写搜索
                    'features': features_list,
                    'generation': generation,
                    'bucket': doc.get('bucket'),
                    'level_min': doc.get('level_min'),
                    'data': json.dumps(doc) # 将整个 doc 作为 JSON 字符串插入
                })
            
            # 执行批量插入
            conn.execute(text(f"""
                INSERT INTO {TABLE_NAME} (id, pokemon_name, features, generation, bucket, level_min, data)
                VALUES (:id, :pokemon_name, :features, :generation, :bucket, :level_min, :data::jsonb)
            """), insert_data)
            
            print(f"已插入 {i + len(batch)} / {len(documents)} 条...")

        # 4. 创建索引
        print("数据插入完毕。正在创建索引以优化搜索...")
        conn.execute(text(f"CREATE INDEX idx_pokemon_name ON {TABLE_NAME} (pokemon_name);"))
        conn.execute(text(f"CREATE INDEX idx_features ON {TABLE_NAME} USING GIN (features);")) # GIN 索引用于数组
        conn.execute(text(f"CREATE INDEX idx_generation ON {TABLE_NAME} (generation);"))
        conn.execute(text(f"CREATE INDEX idx_bucket ON {TABLE_NAME} (bucket);"))
        
        # 提交事务
        conn.commit()

    print("✅ Render Postgres 数据库已成功填充数据！")
    sys.exit(0) # 成功退出

except Exception as e:
    print(f"\n!! 发生错误: {e} !!")
    sys.exit(1) # 退出并导致 build 失败