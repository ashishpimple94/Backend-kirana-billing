const mongoose = require('mongoose');

const BillItemSchema = new mongoose.Schema(
  {
    name: {
      type: String,
      required: true,
      trim: true,
    },
    quantity: {
      type: Number,
      required: true,
      default: 1,
      min: 0,
    },
    unit: {
      type: String,
      default: 'piece',
      trim: true,
    },
    price: {
      type: Number,
      required: true,
      default: 0,
      min: 0,
    },
    amount: {
      type: Number,
      required: true,
      default: 0,
      min: 0,
    },
  },
  { _id: false }
);

const BillSchema = new mongoose.Schema(
  {
    billNumber: {
      type: String,
      required: true,
      unique: true,
      trim: true,
      index: true,
    },
    customerName: {
      type: String,
      default: 'Walk-in Customer',
      trim: true,
    },
    customerMobile: {
      type: String,
      default: '',
      trim: true,
    },
    items: [BillItemSchema],
    subtotal: {
      type: Number,
      required: true,
      default: 0,
    },
    gstRate: {
      type: Number,
      default: 0,
    },
    gstAmount: {
      type: Number,
      default: 0,
    },
    grandTotal: {
      type: Number,
      required: true,
      default: 0,
    },
    paymentMode: {
      type: String,
      enum: ['Cash', 'UPI', 'Credit', 'Pending'],
      default: 'Cash',
    },
    storeName: {
      type: String,
      default: 'किराणा स्टोअर्स',
    },
    transcript: {
      type: String,
      default: '',
    },
    source: {
      type: String,
      enum: ['voice', 'manual', 'scanner'],
      default: 'voice',
    },
  },
  {
    timestamps: true,
  }
);

module.exports = mongoose.model('Bill', BillSchema);

