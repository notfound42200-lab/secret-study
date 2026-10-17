from flask import Flask, render_template, request, session, redirect, url_for, send_from_directory
import razorpay
import os
import secrets
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Flask session secret
app.secret_key = os.getenv("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY is missing from environment variables.")

# Razorpay credentials loaded from your .env file
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
    raise RuntimeError("Razorpay credentials are missing.")

client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)


PRODUCTS = {
    "secret-study": {
        "name": "Instagram Night Studies",
        "price": 99,
        "file": "secret_study_notes.mp4"
    },
    "standard": {
        "name": "Teenager Package",
        "price": 199,
        "file": "standard_notes.mp4"
    },
    "premium": {
        "name": "Premium and Combo",
        "price": 499,
        "file": "premium_notes.mp4"
    }
}


@app.route("/")
def home():
    return render_template("index.html", products=PRODUCTS)


@app.route("/buy/<product_id>")
def buy(product_id):
    product = PRODUCTS.get(product_id)

    if not product:
        return "Product not found.", 404

    amount = product["price"] * 100

    order = client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1,
        "notes": {
            "product_id": product_id
        }
    })

    session_orders = session.get("orders", {})
    session_orders[order["id"]] = product_id
    session["orders"] = session_orders

    return render_template(
        "buy.html",
        product=product,
        product_id=product_id,
        order_id=order["id"],
        key_id=RAZORPAY_KEY_ID,
        amount=amount
    )


@app.route("/payment/verify", methods=["POST"])
def payment_verify():
    payment_id = request.form.get("razorpay_payment_id")
    order_id = request.form.get("razorpay_order_id")
    signature = request.form.get("razorpay_signature")

    orders = session.get("orders", {})
    product_id = orders.get(order_id)
    product = PRODUCTS.get(product_id)

    if not all([payment_id, order_id, signature, product]):
        return "Invalid order.", 400

    try:
        # Verify Razorpay's payment signature.
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature
        })

        # Fetch the server-created order and payment.
        order = client.order.fetch(order_id)
        payment = client.payment.fetch(payment_id)

        expected_amount = product["price"] * 100

        # Confirm the order matches the selected product.
        if (
            order.get("amount") != expected_amount
            or order.get("currency") != "INR"
            or order.get("notes", {}).get("product_id") != product_id
        ):
            return "Order details do not match.", 400

        # Confirm payment belongs to this order and amount.
        if (
            payment.get("order_id") != order_id
            or payment.get("amount") != expected_amount
            or payment.get("currency") != "INR"
            or payment.get("status") != "captured"
        ):
            return "Payment was not captured or is invalid.", 400

        # Grant access to the exact purchased product.
        paid_orders = session.get("paid_orders", {})
        paid_orders[order_id] = product_id
        session["paid_orders"] = paid_orders

        return redirect(url_for(
            "download_file",
            order_id=order_id
        ))

    except Exception:
        app.logger.exception("Payment verification failed")
        return "Payment verification failed.", 400


@app.route("/download/<order_id>")
def download_file(order_id):
    paid_orders = session.get("paid_orders", {})
    product_id = paid_orders.get(order_id)
    product = PRODUCTS.get(product_id)

    if not product:
        return "Verified payment required.", 403

    return send_from_directory(
        os.path.join(app.root_path, "files"),
        product["file"],
        as_attachment=True
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
