// --- PREDICTION LOADING STATE ---
// Disables button and shows spinner when form is submitted
function showLoader() {
    const btn = document.querySelector('button[type="submit"]');
    if (btn) {
        const originalText = btn.innerText;
        btn.disabled = true;
        btn.innerHTML = `<i class="fas fa-spinner fa-spin mr-2"></i> Analyzing...`;
        
        // Safety timeout in case server hangs (re-enable after 15s)
        setTimeout(() => {
            btn.disabled = false;
            btn.innerText = originalText;
        }, 15000);
    }
}

// Attach to predict form
document.addEventListener("DOMContentLoaded", function() {
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', showLoader);
    }
});

// --- M-PESA PAYMENT MODAL LOGIC ---
let currentAmount = 0;
let currentPlan = "";

function openPaymentModal(plan, amount) {
    currentAmount = amount;
    currentPlan = plan;
    
    const modal = document.getElementById('paymentModal');
    const amountLabel = document.getElementById('payAmount');
    
    if (modal && amountLabel) {
        amountLabel.innerText = "KES " + amount;
        modal.classList.remove('hidden');
    } else {
        alert("Payment system initializing... please refresh.");
    }
}

function closePaymentModal() {
    const modal = document.getElementById('paymentModal');
    if (modal) modal.classList.add('hidden');
}

async function triggerMpesa() {
    const phoneInput = document.getElementById('mpesaPhone');
    const statusDiv = document.getElementById('paymentStatus');
    const btn = document.getElementById('payBtn');
    
    const phone = phoneInput.value;
    
    // Basic validation (Kenyan number format)
    if (!phone.match(/^(?:254|\+254|0)?(7(?:(?:[129][0-9])|(?:0[0-8])|(4[0-1]))[0-9]{6})$/)) {
        statusDiv.innerText = "❌ Invalid Phone Number";
        statusDiv.className = "text-red-500 text-sm font-bold mt-2";
        statusDiv.classList.remove('hidden');
        return;
    }

    // UI Update
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sending...';
    statusDiv.classList.add('hidden');

    try {
        const formData = new FormData();
        formData.append('phone_number', phone);
        formData.append('amount', currentAmount);

        const response = await fetch('/mpesa/stkpush', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            statusDiv.innerText = "✅ Request Sent! Check your phone to enter PIN.";
            statusDiv.className = "text-green-500 text-sm font-bold mt-2";
            statusDiv.classList.remove('hidden');
            
            // Redirect after 5 seconds to profile
            setTimeout(() => {
                window.location.href = "/profile";
            }, 5000);
        } else {
            throw new Error(result.error || "Payment Failed");
        }

    } catch (error) {
        console.error(error);
        statusDiv.innerText = "❌ Error: " + error.message;
        statusDiv.className = "text-red-500 text-sm font-bold mt-2";
        statusDiv.classList.remove('hidden');
        btn.disabled = false;
        btn.innerText = "Pay Now";
    }
}