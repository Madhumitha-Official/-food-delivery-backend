from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlite3
import hashlib
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "food_delivery.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            rating REAL DEFAULT 0,
            city TEXT,
            image_url TEXT,
            owner_id INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database
init_db()

# ============ SCHEMAS ============
class UserCreate(BaseModel):
    email: str
    username: str
    password: str
    full_name: Optional[str] = None

class RestaurantCreate(BaseModel):
    name: str
    description: Optional[str] = None
    city: Optional[str] = None
    image_url: Optional[str] = None

# ============ API ENDPOINTS ============

@app.get("/")
def root():
    return {"message": "Food Delivery API Running!", "status": "success"}

@app.get("/test")
def test():
    return {"message": "API is working!"}

@app.post("/register")
def register(user: UserCreate):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check username
        cursor.execute("SELECT * FROM users WHERE username = ?", (user.username,))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="Username already taken")
        
        # Check email
        cursor.execute("SELECT * FROM users WHERE email = ?", (user.email,))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Simple MD5 hash (for demo only!)
        hashed_password = hashlib.md5(user.password.encode()).hexdigest()
        
        # Insert user
        cursor.execute(
            "INSERT INTO users (email, username, password, full_name) VALUES (?, ?, ?, ?)",
            (user.email, user.username, hashed_password, user.full_name)
        )
        conn.commit()
        conn.close()
        
        return {"message": "User created successfully!", "username": user.username}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/login")
def login(username: str, password: str):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        hashed_password = hashlib.md5(password.encode()).hexdigest()
        cursor.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, hashed_password)
        )
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Simple token (for demo)
        import jwt
        import datetime
        
        token_data = {
            "username": username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }
        token = jwt.encode(token_data, "secretkey", algorithm="HS256")
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "username": username
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/restaurants")
def get_restaurants():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM restaurants")
        restaurants = cursor.fetchall()
        conn.close()
        
        return [
            {
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "rating": r[3],
                "city": r[4],
                "image_url": r[5]
            }
            for r in restaurants
        ]
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/restaurants")
def create_restaurant(restaurant: RestaurantCreate):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO restaurants (name, description, city, image_url) VALUES (?, ?, ?, ?)",
            (restaurant.name, restaurant.description, restaurant.city, restaurant.image_url)
        )
        conn.commit()
        conn.close()
        
        return {"message": "Restaurant created!", "name": restaurant.name}
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/restaurants/{restaurant_id}")
def get_restaurant(restaurant_id: int):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM restaurants WHERE id = ?", (restaurant_id,))
        restaurant = cursor.fetchone()
        conn.close()
        
        if not restaurant:
            raise HTTPException(status_code=404, detail="Restaurant not found")
        
        return {
            "id": restaurant[0],
            "name": restaurant[1],
            "description": restaurant[2],
            "rating": restaurant[3],
            "city": restaurant[4],
            "image_url": restaurant[5]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
# ============ ORDERS ============

class OrderItem(BaseModel):
    name: str
    price: float
    quantity: int

class OrderCreate(BaseModel):
    username: str
    items: list[OrderItem]
    total_price: float
    delivery_address: Optional[str] = "Chennai"

def init_orders_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            items TEXT NOT NULL,
            total_price REAL NOT NULL,
            delivery_address TEXT,
            status TEXT DEFAULT 'placed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_orders_db()

@app.post("/api/orders")
def create_order(order: OrderCreate):
    try:
        import json
        conn = get_db()
        cursor = conn.cursor()
        
        items_json = json.dumps([
            {"name": i.name, "price": i.price, "quantity": i.quantity}
            for i in order.items
        ])
        
        cursor.execute(
            """INSERT INTO orders 
            (username, items, total_price, delivery_address, status) 
            VALUES (?, ?, ?, ?, ?)""",
            (order.username, items_json, order.total_price, 
             order.delivery_address, 'placed')
        )
        conn.commit()
        order_id = cursor.lastrowid
        conn.close()
        
        return {
            "message": "Order placed successfully!",
            "order_id": order_id,
            "status": "placed"
        }
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/orders/{username}")
def get_orders(username: str):
    try:
        import json
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM orders WHERE username = ? ORDER BY created_at DESC",
            (username,)
        )
        orders = cursor.fetchall()
        conn.close()
        
        return [
            {
                "id": o[0],
                "username": o[1],
                "items": json.loads(o[2]),
                "total_price": o[3],
                "delivery_address": o[4],
                "status": o[5],
                "created_at": o[6]
            }
            for o in orders
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/orders/{order_id}/status")
def update_order_status(order_id: int, status: str):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (status, order_id)
        )
        conn.commit()
        conn.close()
        return {"message": "Status updated!", "status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.get("/api/orders/id/{order_id}")
def get_order_by_id(order_id: int):
    try:
        import json
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        conn.close()
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        return {
            "id": order[0],
            "username": order[1],
            "items": json.loads(order[2]),
            "total_price": order[3],
            "delivery_address": order[4],
            "status": order[5],
            "created_at": order[6]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/orders/all")
def get_all_orders():
    try:
        import json
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders ORDER BY created_at DESC")
        orders = cursor.fetchall()
        conn.close()
        
        return [
            {
                "id": o[0],
                "username": o[1],
                "items": json.loads(o[2]),
                "total_price": o[3],
                "delivery_address": o[4],
                "status": o[5],
                "created_at": o[6]
            }
            for o in orders
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))