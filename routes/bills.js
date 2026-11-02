const express = require('express');
const Bill = require('../models/Bill');

const router = express.Router();

/**
 * POST /api/bills
 * Save a newly created bill to MongoDB
 */
router.post('/', async (req, res) => {
  try {
    const {
      billNumber,
      customerName,
      customerMobile,
      items,
      subtotal,
      gstRate,
      gstAmount,
      grandTotal,
      paymentMode,
      storeName,
      transcript,
      source,
    } = req.body;

    if (!billNumber) {
      return res.status(400).json({ error: 'Bill number is required' });
    }

    if (!items || !Array.isArray(items) || items.length === 0) {
      return res.status(400).json({ error: 'Bill must contain at least 1 item' });
    }

    const calculatedSubtotal =
      subtotal !== undefined
        ? parseFloat(subtotal)
        : items.reduce((sum, it) => sum + (parseFloat(it.amount || it.quantity * it.price) || 0), 0);

    const calcGstRate = parseFloat(gstRate) || 0;
    const calcGstAmount =
      gstAmount !== undefined
        ? parseFloat(gstAmount)
        : Math.round(((calculatedSubtotal * calcGstRate) / 100) * 100) / 100;

    const calcGrandTotal =
      grandTotal !== undefined
        ? parseFloat(grandTotal)
        : Math.round((calculatedSubtotal + calcGstAmount) * 100) / 100;

    // Check if bill with this billNumber already exists; if so, update or generate unique suffix
    let finalBillNumber = billNumber;
    const existing = await Bill.findOne({ billNumber });
    if (existing) {
      finalBillNumber = `${billNumber}-${Math.floor(100 + Math.random() * 900)}`;
    }

    const bill = new Bill({
      billNumber: finalBillNumber,
      customerName: customerName || 'Walk-in Customer',
      customerMobile: customerMobile || '',
      items: items.map((it) => ({
        name: it.name || 'Item',
        quantity: parseFloat(it.quantity || it.qty || 1) || 1,
        unit: it.unit || 'piece',
        price: parseFloat(it.price || 0) || 0,
        amount: parseFloat(it.amount || (it.quantity || 1) * (it.price || 0)) || 0,
      })),
      subtotal: calculatedSubtotal,
      gstRate: calcGstRate,
      gstAmount: calcGstAmount,
      grandTotal: calcGrandTotal,
      paymentMode: paymentMode || 'Cash',
      storeName: storeName || 'किराणा स्टोअर्स',
      transcript: transcript || '',
      source: source || 'voice',
    });

    const saved = await bill.save();
    console.log(`[POST /api/bills] Bill saved successfully in MongoDB: ${saved.billNumber} (Total: ₹${saved.grandTotal})`);

    res.status(201).json({
      success: true,
      message: 'पावती डेटाबेसमध्ये यशस्वीरीत्या जतन केली!',
      bill: saved,
    });
  } catch (err) {
    console.error('[POST /api/bills] Error saving bill:', err);
    res.status(500).json({
      error: 'पावती डेटाबेसमध्ये सेव्ह करताना त्रुटी आली.',
      details: err.message,
    });
  }
});

/**
 * GET /api/bills
 * Retrieve bill history from MongoDB
 */
router.get('/', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit, 10) || 50;
    const page = parseInt(req.query.page, 10) || 1;
    const skip = (page - 1) * limit;

    const [bills, total] = await Promise.all([
      Bill.find().sort({ createdAt: -1 }).skip(skip).limit(limit),
      Bill.countDocuments(),
    ]);

    res.json({
      success: true,
      total,
      page,
      limit,
      bills,
    });
  } catch (err) {
    console.error('[GET /api/bills] Error fetching bills:', err);
    res.status(500).json({
      error: 'पावत्या लोड करताना त्रुटी आली.',
      details: err.message,
    });
  }
});

/**
 * GET /api/bills/:id
 * Retrieve a specific bill
 */
router.get('/:id', async (req, res) => {
  try {
    const { id } = req.params;
    let bill = null;
    if (id.match(/^[0-9a-fA-F]{24}$/)) {
      bill = await Bill.findById(id);
    }
    if (!bill) {
      bill = await Bill.findOne({ billNumber: id });
    }

    if (!bill) {
      return res.status(404).json({ error: 'Bill not found' });
    }

    res.json({ success: true, bill });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/**
 * DELETE /api/bills/:id
 * Delete a bill from MongoDB
 */
router.delete('/:id', async (req, res) => {
  try {
    const { id } = req.params;
    let deleted = null;
    if (id.match(/^[0-9a-fA-F]{24}$/)) {
      deleted = await Bill.findByIdAndDelete(id);
    }
    if (!deleted) {
      deleted = await Bill.findOneAndDelete({ billNumber: id });
    }

    if (!deleted) {
      return res.status(404).json({ error: 'Bill not found' });
    }

    console.log(`[DELETE /api/bills/:id] Bill deleted: ${deleted.billNumber}`);
    res.json({ success: true, message: 'पावती डेटाबेसमधून हटवली.' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;

