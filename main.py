from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import threading

app = FastAPI(title="Food-Delivery API")

order_id_seq = 1

# To avoid errors when multiple threads change data
db_lock = threading.Lock()

class Order(BaseModel):
    order_id: int
    description: str
    status: str = Field(default="Pending")
    amount: float

orders_db: Dict[int, Order] = {}
cancellation_reasons: Dict[int, str] = {}

class OrderStatusUpdate(BaseModel):
    status: str
    cancellation_reason: Optional[str] = None

VALID_STATUSES = ["Pending", "Successful", "Cancelled"]

#  Creating new orders with order details 

@app.post("/orders/", response_model=Order)
def create_order(order: Order):
    global order_id_seq
    with db_lock:
        order.order_id = order_id_seq
        if order.status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status value.")
        orders_db[order_id_seq] = order
        order_id_seq += 1
    return order

#  Retrieving a list of all orders 

@app.get("/orders/", response_model=List[Order])
def list_orders():
    return list(orders_db.values())

#  Returning a basic summary of the total number of orders and total value 

@app.get("/orders/summary")
def get_order_summary():
    total_orders = len(orders_db)
    total_amount = sum(order.amount for order in orders_db.values())
    return {
        "total_orders": total_orders,
        "total_amount": total_amount
    }

# Fetching a single order by ID 

@app.get("/orders/{order_id}")
def get_order(order_id: int):
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    response = order.dict()
    if order.status == "Cancelled":
        reason = cancellation_reasons.get(order_id, "No reason provided")
        response["cancellation_reason"] = reason
    return response

#  Updating the status of an order 

@app.put("/orders/{order_id}", response_model=Order)
def update_order_status(order_id: int, update: OrderStatusUpdate):
    if update.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status value.")

    with db_lock:
        order = orders_db.get(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        current_status = order.status

        if current_status == "Successful":
            raise HTTPException(status_code=400, detail="Order is already successful and cannot be updated.")
        if current_status == "Cancelled":
            raise HTTPException(status_code=400, detail="Order is already cancelled. Please create a new order.")

        if current_status == "Pending":
            if update.status == "Cancelled":
                reason = update.cancellation_reason or "No reason provided"
                cancellation_reasons[order_id] = reason
                order.status = "Cancelled"
            elif update.status == "Successful":
                order.status = "Successful"
            else:
                raise HTTPException(status_code=400, detail="Invalid status update from Pending.")

        return order
