import sys
import os
import asyncio
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

# --- PATH SETUP ---
# Ensures we can find the AI Brain (main.py)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path: sys.path.insert(0, project_root)

# Import M-Pesa Utils (Graceful fallback if missing)
try:
    from mpesa_utils import initiate_stk_push
except ImportError:
    def initiate_stk_push(phone, amount): return {"ResponseCode": "0", "CustomerMessage": "Simulated Success"}

# Import AI Engine
try:
    from main import MatchPredictor
    ai_engine = MatchPredictor()
    print("✅ AI Engine Online")
except Exception as e:
    print(f"⚠️ AI Engine Offline: {e}")
    ai_engine = None

# STATES
PHONE, PAYMENT_CONFIRM = range(2)

# --- YOUR CREDENTIALS ---
TOKEN = "8379170828:AAF3PpY_TDosvr-gfBasP-0igTdJ4f3UnZ4" 

# --- COMMANDS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ *Welcome to ScorePulse Premium Bot!*\n\n"
        "I provide AI-driven football analysis.\n\n"
        "👇 *Menu:*\n"
        "/predict <Home> <Away> - Free Single Analysis\n"
        "/buy - Get 10 Premium Sure Bets (KES 50)",
        parse_mode='Markdown'
    )

async def predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ai_engine:
        await update.message.reply_text("⚠️ AI Brain is waking up... Try again in 10s.")
        return
        
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ Usage: /predict Arsenal Chelsea")
        return

    home, away = args[0], args[1]
    await update.message.reply_text(f"🔍 Analyzing {home} vs {away}...")
    
    try:
        # We assume 'gold' tier for single bot predictions to show full capabilities
        res = ai_engine.predict_for_web(home, away, 'gold')
        
        if "error" in res:
            await update.message.reply_text(f"❌ Error: {res['error']}")
            return

        win = res['win_prob']
        # Determine the tip
        if win['home'] > 55: tip = f"Home Win ({win['home']}%)"
        elif win['away'] > 55: tip = f"Away Win ({win['away']}%)"
        elif res['over25'] > 60: tip = f"Over 2.5 Goals ({res['over25']}%)"
        else: tip = "Draw / Risky Match"

        msg = (
            f"🏆 *{res['home']} vs {res['away']}*\n"
            f"━━━━━━━━━━━━━━\n"
            f"💡 **AI Tip:** {tip}\n"
            f"━━━━━━━━━━━━━━\n"
            f"🏠 Home: {win['home']}%\n"
            f"🤝 Draw: {win['draw']}%\n"
            f"✈️ Away: {win['away']}%\n\n"
            f"⚽ Exp. Goals: {res['total_goals']}\n"
            f"🔄 BTTS: {res['btts']}%\n"
            f"🧠 Confidence: {res['confidence']['label']}"
        )
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)}")

# --- BUY FLOW ---

async def buy_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💎 *Premium Package*\n"
        "Get 10 High-Confidence Tips for **KES 50**.\n\n"
        "Enter your M-Pesa Number (e.g., 0712345678):", 
        parse_mode='Markdown'
    )
    return PHONE

async def process_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text
    await update.message.reply_text(f"📲 Sending prompt to {phone}...")
    
    # Trigger M-Pesa STK Push
    resp = initiate_stk_push(phone, 50)
    
    if "ResponseCode" in resp: 
        kb = [['I Have Paid ✅', 'Cancel ❌']]
        reply_markup = ReplyKeyboardMarkup(kb, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "🔔 check your phone for the PIN prompt.\n\nClick **'I Have Paid'** below once completed.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return PAYMENT_CONFIRM
    else:
        await update.message.reply_text("❌ Payment Failed. Check number and try again.")
        return ConversationHandler.END

async def deliver_predictions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == 'Cancel ❌':
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    await update.message.reply_text("✅ Payment Verified! Generating slip...", reply_markup=ReplyKeyboardRemove())
    
    if ai_engine:
        # Fetch 10 High-Confidence Games
        games = ai_engine.get_premium_batch(10)
        
        if not games:
            await update.message.reply_text("⚠️ No high-confidence matches found right now.")
            return ConversationHandler.END

        msg = "🔥 **SCOREPULSE PREMIUM SLIP** 🔥\n\n"
        for g in games:
            probs = g['win_prob']
            if probs['home'] > 50: tip = "1"
            elif probs['away'] > 50: tip = "2"
            elif g['over25'] > 60: tip = "OV2.5"
            else: tip = "X"
            
            msg += f"⚽ {g['home']} vs {g['away']}\n💡 Tip: *{tip}* ({g['confidence']['label']})\n\n"
            
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# --- STARTUP CHECK ---
async def post_init(application):
    bot = await application.bot.get_me()
    print(f"🤖 CONNECTED SUCCESSFULLY TO: @{bot.username}")
    print(f"🆔 Bot ID: {bot.id}")

if __name__ == '__main__':
    # Initialize Bot
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("predict", predict))
    
    buy_conv = ConversationHandler(
        entry_points=[CommandHandler("buy", buy_start)],
        states={
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_payment)],
            PAYMENT_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, deliver_predictions)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(buy_conv)
    
    print("🚀 Bot starting...")
    app.run_polling()