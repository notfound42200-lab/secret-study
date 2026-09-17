from flask import Flask, render_template, request, session, redirect, url_for, send_from_directory
import razorpay
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Flask session secret
app.secret_key = "my-file-store-secret-839274"

# Razorpay TEST credentials
# Put your NEW credentials here.
# DO NOT send the secret to me.
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/buy")
def buy():
    amount = 99 * 100

    order = client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })

    # Save the server-created order ID
    session["order_id"] = order["id"]

    return render_template(
        "buy.html",
        order_id=order["id"],
        key_id=RAZORPAY_KEY_ID,
        amount=amount
    )


@app.route("/payment/verify", methods=["POST"])
def payment_verify():

    payment_id = request.form.get("razorpay_payment_id")
    order_id = request.form.get("razorpay_order_id")
    signature = request.form.get("razorpay_signature")


    try:
        # Verify the Razorpay signature on the server
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature
        })

        # Check payment status
        payment = client.payment.fetch(payment_id)

        if payment["status"] != "captured":
            return "Payment was not captured.", 400

        # Payment is verified
        session["paid"] = True

        return redirect(url_for("download_file"))

    except Exception as e:
        print("Payment verification error:", e)
        return "Payment verification failed.", 400


@app.route("/download")
def download_file():

    # Don't allow downloading without verified payment
    if not session.get("paid"):
        return "Payment required.", 403

    return send_from_directory(
        "files",
        "c_programming_notes.pdf",
        as_attachment=True
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)