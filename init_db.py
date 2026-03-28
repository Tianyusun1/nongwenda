import pymysql
import time

# ================= 1. 配置信息 =================
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': '123456',
    'charset': 'utf8mb4'
}
DB_NAME = 'agri_qa'


def init_database():
    print("🚀 开始初始化农产品良种客服数据库...")

    connection = None
    try:
        # 1. 连接 MySQL 服务器
        connection = pymysql.connect(**DB_CONFIG)

        with connection.cursor() as cursor:
            # 2. 彻底清理旧库 (解决 Unknown column 报错的关键)
            print(f"⚠️ 正在清理旧的数据库 '{DB_NAME}'...")
            cursor.execute(f"DROP DATABASE IF EXISTS {DB_NAME};")

            # 3. 创建全新数据库
            print(f"🏗️ 正在创建全新的数据库 '{DB_NAME}'...")
            sql = f"CREATE DATABASE {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            cursor.execute(sql)

        connection.commit()
        print(f"✅ 数据库 '{DB_NAME}' 已重置成功！")
        print("--------------------------------------------------")
        print("💡 下一步操作：")
        print("   1. 现在你可以直接运行 'python app.py'。")
        print("   2. 系统会自动在空库中创建最新的表结构（含密码和角色字段）。")
        print("   3. 系统会自动为你生成管理员账号：admin / 123456")
        print("--------------------------------------------------")

    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        print("请检查：1. MySQL是否启动  2. 账号密码是否正确  3. 是否安装了 cryptography 包")
    finally:
        if connection:
            connection.close()


if __name__ == '__main__':
    # 给用户一个反悔的机会，防止误删
    confirm = input("⚠️ 该操作将清空所有聊天记录和用户信息，确认重置吗？(y/n): ")
    if confirm.lower() == 'y':
        init_database()
    else:
        print("操作已取消。")