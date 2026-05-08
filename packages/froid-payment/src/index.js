require('dotenv').config();
const express = require('express');
const cors = require('cors');
const { Pool } = require('pg');
const fetch = require('node-fetch');

const app = express();
app.use(cors());
app.use(express.json());

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

const PLANS = {
  pay_per_session: { amount: 15, credits: 1 },
  package_10: { amount: 120, credits: 10 },
  package_50: { amount: 500, credits: 50 },
  unlimited_monthly: { amount: 299, credits: 999999 },
};

// Criar pagamento Mercado Pago (PIX)
app.post('/payment/mercadopago', async (req, res) => {
  try {
    const { userId, planType } = req.body;
    const plan = PLANS[planType];
    if (!plan) return res.status(400).json({ error: 'Plano inválido' });

    const response = await fetch('https://api.mercadopago.com/checkout/preferences', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.MERCADOPAGO_ACCESS_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        items: [{
          title: `FROID - ${planType}`,
          quantity: 1,
          currency_id: 'BRL',
          unit_price: plan.amount,
        }],
        payment_methods: {
          excluded_payment_types: [{ id: 'credit_card' }, { id: 'debit_card' }],
        },
        back_urls: {
          success: `${process.env.FRONTEND_URL}/payment/success`,
          failure: `${process.env.FRONTEND_URL}/payment/failure`,
        },
        notification_url: `${process.env.BACKEND_WEBHOOK_URL}/mercadopago`,
        external_reference: userId,
      }),
    });

    const preference = await response.json();

    const result = await pool.query(
      `INSERT INTO transactions (id, "userId", type, status, amount, "paymentMethod", gateway, "gatewayOrderId", "pixQrCode", "createdAt", "updatedAt")
       VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
       RETURNING id`,
      [userId, 'subscription_purchase', 'pending', plan.amount, 'pix', 'mercadopago', preference.id, preference.init_point]
    );

    res.json({
      transactionId: result.rows[0].id,
      checkoutUrl: preference.init_point,
      amount: plan.amount,
    });
  } catch (error) {
    console.error('Erro Mercado Pago:', error);
    res.status(500).json({ error: error.message });
  }
});

// Criar pagamento Stripe (Cartão)
app.post('/payment/stripe', async (req, res) => {
  try {
    const { userId, planType } = req.body;
    const plan = PLANS[planType];
    if (!plan) return res.status(400).json({ error: 'Plano inválido' });

    const params = new URLSearchParams({
      'payment_method_types[]': 'card',
      'line_items[0][price_data][currency]': 'brl',
      'line_items[0][price_data][product_data][name]': `FROID - ${planType}`,
      'line_items[0][price_data][unit_amount]': (plan.amount * 100).toString(),
      'line_items[0][quantity]': '1',
      'mode': 'payment',
      'success_url': `${process.env.FRONTEND_URL}/payment/success?session_id={CHECKOUT_SESSION_ID}`,
      'cancel_url': `${process.env.FRONTEND_URL}/payment/failure`,
      'client_reference_id': userId,
      'metadata[planType]': planType,
      'metadata[userId]': userId,
    });

    const response = await fetch('https://api.stripe.com/v1/checkout/sessions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.STRIPE_SECRET_KEY}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: params,
    });

    const session = await response.json();

    const result = await pool.query(
      `INSERT INTO transactions (id, "userId", type, status, amount, "paymentMethod", gateway, "gatewayOrderId", "createdAt", "updatedAt")
       VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, NOW(), NOW())
       RETURNING id`,
      [userId, 'subscription_purchase', 'pending', plan.amount, 'credit_card', 'stripe', session.id]
    );

    res.json({
      transactionId: result.rows[0].id,
      checkoutUrl: session.url,
      sessionId: session.id,
      amount: plan.amount,
    });
  } catch (error) {
    console.error('Erro Stripe:', error);
    res.status(500).json({ error: error.message });
  }
});

// Webhook Mercado Pago
app.post('/webhook/mercadopago', async (req, res) => {
  try {
    if (req.body.type === 'payment') {
      const paymentId = req.body.data.id;
      
      const response = await fetch(`https://api.mercadopago.com/v1/payments/${paymentId}`, {
        headers: { 'Authorization': `Bearer ${process.env.MERCADOPAGO_ACCESS_TOKEN}` },
      });
      
      const payment = await response.json();

      if (payment.status === 'approved') {
        await pool.query(
          `UPDATE transactions SET status = $1, "paidAt" = NOW(), "pixTxId" = $2, "updatedAt" = NOW()
           WHERE "gatewayOrderId" = $3`,
          ['paid', payment.id.toString(), payment.preference_id]
        );

        const txResult = await pool.query(
          `SELECT * FROM transactions WHERE "gatewayOrderId" = $1 LIMIT 1`,
          [payment.preference_id]
        );

        if (txResult.rows.length > 0) {
          await activateSubscription(payment.external_reference, parseFloat(txResult.rows[0].amount));
        }
      }
    }
    res.json({ status: 'ok' });
  } catch (error) {
    console.error('Erro webhook MP:', error);
    res.status(500).json({ error: error.message });
  }
});

// Webhook Stripe
app.post('/webhook/stripe', async (req, res) => {
  try {
    const event = req.body;
    
    if (event.type === 'checkout.session.completed') {
      const session = event.data.object;
      const userId = session.client_reference_id;

      await pool.query(
        `UPDATE transactions SET status = $1, "paidAt" = NOW(), "updatedAt" = NOW()
         WHERE "gatewayOrderId" = $2`,
        ['paid', session.id]
      );

      const txResult = await pool.query(
        `SELECT * FROM transactions WHERE "gatewayOrderId" = $1 LIMIT 1`,
        [session.id]
      );

      if (txResult.rows.length > 0) {
        await activateSubscription(userId, parseFloat(txResult.rows[0].amount));
      }
    }
    res.json({ status: 'ok' });
  } catch (error) {
    console.error('Erro webhook Stripe:', error);
    res.status(500).json({ error: error.message });
  }
});

async function activateSubscription(userId, amount) {
  const planMap = {
    15: { type: 'pay_per_session', credits: 1 },
    120: { type: 'package_10', credits: 10 },
    500: { type: 'package_50', credits: 50 },
    299: { type: 'unlimited_monthly', credits: 999999, expiry: 30 },
  };

  const plan = planMap[amount];
  if (!plan) return;

  const expiryDate = plan.expiry 
    ? new Date(Date.now() + plan.expiry * 24 * 60 * 60 * 1000).toISOString()
    : null;

  await pool.query(
    `INSERT INTO subscriptions (id, "userId", "planType", status, "creditsTotal", "creditsRemaining", amount, "paymentMethod", "expiryDate", "createdAt", "updatedAt")
     VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())`,
    [userId, plan.type, 'active', plan.credits, plan.credits, amount, 'card', expiryDate]
  );
}

app.listen(process.env.PORT, () => {
  console.log(`🚀 FROID Payment running on port ${process.env.PORT}`);
});
