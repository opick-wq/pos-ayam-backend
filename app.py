from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime
import random
import string

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pos_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ==========================================
# 1. MODEL DATABASE
# ==========================================
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    image = db.Column(db.String(50), default='🍽️')
    category = db.Column(db.String(50), default='Makanan')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_code = db.Column(db.String(20), unique=True, nullable=False)
    customer_name = db.Column(db.String(100), default='Pelanggan')
    customer_phone = db.Column(db.String(20), default='-') 
    table_number = db.Column(db.String(10), default='-')   
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship('OrderItem', backref='order', cascade="all, delete-orphan")

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=True) # Boleh kosong jika produk dihapus
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')

with app.app_context():
    db.create_all()
    if not Product.query.first():
        db.session.add_all([
            Product(name="Ikan Nila", price=16000, stock=50, image="🐟", category="Makanan"),
            Product(name="Ikan Lele", price=12000, stock=50, image="🐟", category="Makanan"),
            Product(name="Ayam Paha", price=22000, stock=50, image="🍗", category="Makanan"),
            Product(name="Sate Paru", price=8000, stock=50, image="🍢", category="Makanan"),
            Product(name="Nasi Putih", price=6000, stock=50, image="🍚", category="Makanan"),
            Product(name="Jukut Goreng", price=5000, stock=50, image="🥬", category="Makanan"),
            Product(name="Es Jeruk", price=8000, stock=50, image="🍊", category="Minuman"),
            Product(name="Es Teh", price=6000, stock=50, image="🍹", category="Minuman"),
        ])
        db.session.commit()

# ==========================================
# 2. API ENDPOINTS
# ==========================================
@app.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    # Tangani Preflight Request secara eksplisit jika diperlukan (meskipun CORS(app) biasanya sudah cukup)
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    data = request.json
    if data and data.get('email') == 'admin@ayamcabeijo.com' and data.get('password') == 'admin123':
        return jsonify({"token": "auth-token-valid-123"}), 200
    
    return jsonify({"error": "Email atau password salah!"}), 401


@app.route('/api/products', methods=['GET', 'POST'])
def handle_products():
    if request.method == 'GET':
        products = Product.query.all()
        return jsonify([{"id": p.id, "name": p.name, "price": p.price, "stock": p.stock, "image": p.image, "category": p.category} for p in products]), 200
    if request.method == 'POST':
        data = request.json
        new_prod = Product(name=data['name'], price=float(data['price']), stock=int(data['stock']), image=data.get('image', '🍽️'), category=data.get('category', 'Makanan'))
        db.session.add(new_prod)
        db.session.commit()
        return jsonify({"message": "Produk ditambahkan!"}), 201

@app.route('/api/products/<int:id>', methods=['PUT', 'DELETE'])
def update_delete_product(id):
    product = Product.query.get_or_404(id)
    if request.method == 'PUT':
        data = request.json
        product.name = data['name']; product.price = float(data['price']); product.stock = int(data['stock']); product.image = data.get('image', product.image); product.category = data.get('category', product.category)
        db.session.commit()
        return jsonify({"message": "Produk diperbarui!"}), 200
    if request.method == 'DELETE':
        db.session.delete(product)
        db.session.commit()
        return jsonify({"message": "Produk dihapus!"}), 200

# API UNTUK ADMIN (Semua Pesanan - DIUBAH AGAR AMAN JIKA PRODUK DIHAPUS)
@app.route('/api/orders', methods=['POST', 'GET'])
def handle_orders():
    if request.method == 'GET':
        orders = Order.query.order_by(Order.created_at.desc()).all()
        res = [{"id": o.id, "code": o.order_code, "customer_name": o.customer_name, "phone": o.customer_phone, "table": o.table_number, "total": o.total_price, "status": o.status, "date": o.created_at.strftime("%d/%m/%Y %H:%M"), "items": [{"name": i.product.name if i.product else "Produk Dihapus", "qty": i.quantity, "price": i.product.price if i.product else 0} for i in o.items]} for o in orders]
        return jsonify(res), 200

    data = request.json
    cart_items = data.get('cart', [])
    order_code = f"ORD-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
    
    new_order = Order(
        order_code=order_code, 
        customer_name=data.get('customer_name', 'Pelanggan'),
        customer_phone=data.get('customer_phone', '-'),
        table_number=data.get('table_number', '-'),
        total_price=0, 
        status='Pending'
    )
    db.session.add(new_order)
    db.session.flush()

    total_price = 0
    for item in cart_items:
        product = Product.query.get(item['id'])
        if product and product.stock < item['qty']: return jsonify({"error": f"Stok {product.name} habis."}), 400
        if product:
            sub = product.price * item['qty']
            total_price += sub
            db.session.add(OrderItem(order_id=new_order.id, product_id=product.id, quantity=item['qty'], subtotal=sub))

    new_order.total_price = total_price
    db.session.commit()
    return jsonify({"order_code": order_code, "total": total_price}), 201

# API UNTUK PELANGGAN (Cari Riwayat via No HP)
@app.route('/api/orders/history/<phone>', methods=['GET'])
def get_customer_history(phone):
    orders = Order.query.filter_by(customer_phone=phone).order_by(Order.created_at.desc()).all()
    res = [{"code": o.order_code, "name": o.customer_name, "table": o.table_number, "total": o.total_price, "status": o.status, "date": o.created_at.strftime("%d/%m/%Y %H:%M"), "items": [{"name": i.product.name if i.product else "Produk Dihapus", "qty": i.quantity, "price": i.product.price if i.product else 0} for i in o.items]} for o in orders]
    return jsonify(res), 200

@app.route('/api/orders/manual', methods=['POST'])
def manual_checkout():
    data = request.json
    cart_items = data.get('cart', [])
    order_code = f"MNL-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
    
    new_order = Order(
        order_code=order_code, 
        customer_name=data.get('customer_name', 'Offline'),
        customer_phone='-',
        table_number=data.get('table_number', '-'),
        total_price=0, status='Paid'
    )
    db.session.add(new_order)
    db.session.flush()

    total_price = 0
    for item in cart_items:
        product = Product.query.get(item['id'])
        if product and product.stock < item['qty']: return jsonify({"error": f"Stok {product.name} habis."}), 400
        if product:
            product.stock -= item['qty']
            sub = product.price * item['qty']
            total_price += sub
            db.session.add(OrderItem(order_id=new_order.id, product_id=product.id, quantity=item['qty'], subtotal=sub))

    new_order.total_price = total_price
    db.session.commit()
    items_data = [{"name": i.product.name if i.product else "Produk Dihapus", "qty": i.quantity, "price": i.product.price if i.product else 0} for i in new_order.items]
    return jsonify({"code": order_code, "customer_name": new_order.customer_name, "total": total_price, "items": items_data, "date": new_order.created_at.strftime("%d/%m/%Y %H:%M")}), 201

@app.route('/api/orders/<code>/pay', methods=['POST'])
def pay_order(code):
    order = Order.query.filter_by(order_code=code).first()
    if not order or order.status == 'Paid': return jsonify({"error": "Pesanan tidak valid"}), 400
    for item in order.items:
        if item.product:
            if item.product.stock < item.quantity: return jsonify({"error": f"Stok {item.product.name} tidak cukup."}), 400
            item.product.stock -= item.quantity
    order.status = 'Paid'
    db.session.commit()
    items_data = [{"name": i.product.name if i.product else "Produk Dihapus", "qty": i.quantity, "price": i.product.price if i.product else 0} for i in order.items]
    return jsonify({"code": order.order_code, "customer_name": order.customer_name, "total": order.total_price, "items": items_data, "date": order.created_at.strftime("%d/%m/%Y %H:%M")}), 200

# DIUBAH AGAR AMAN JIKA PRODUK DIHAPUS
@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    paid_orders = Order.query.filter_by(status='Paid').all()
    product_sales = {}
    for order in paid_orders:
        for item in order.items:
            # Pengaman jika produk sudah dihapus
            p_name = item.product.name if item.product else "Menu Dihapus"
            product_sales[p_name] = product_sales.get(p_name, 0) + item.quantity
            
    chart_data = [{"name": k, "terjual": v} for k, v in product_sales.items()]
    return jsonify({
        "revenue": sum(o.total_price for o in paid_orders),
        "total_orders": len(paid_orders),
        "low_stock": [{"name": p.name, "stock": p.stock} for p in Product.query.filter(Product.stock < 10).all()],
        "chart_data": chart_data
    }), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)