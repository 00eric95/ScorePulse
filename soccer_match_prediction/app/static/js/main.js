// =============================================
// SCORE_PULSE MAIN JAVASCRIPT
// =============================================

// --- GLOBAL VARIABLES ---
let currentAmount = 0;
let currentPlan = "";
let metricModal = null;

// --- METRIC EXPLANATION SYSTEM ---
const metricExplanations = {
    'rating': {
        title: 'Power Rating',
        subtitle: 'Team Strength Score (0-100)',
        description: 'Our proprietary AI-powered rating system that combines team performance, recent form, head-to-head records, home/away advantage, and 25+ statistical metrics into a single comprehensive score. Higher ratings indicate stronger teams.',
        example: 'A rating of 85+ suggests a top-tier team likely to finish in Champions League positions. Ratings between 70-84 indicate strong contenders for European qualification.',
        formula: 'Weighted average of offensive & defensive metrics'
    },
    'ppg': {
        title: 'Points Per Game',
        subtitle: 'Average League Points',
        description: 'Average number of points earned per match in the current season. Calculated by dividing total points by number of matches played. The most reliable indicator of team strength and consistency over a full season.',
        example: 'A team with 18 points from 6 games has a PPG of 3.0 (perfect record). Premier League champions typically finish with PPG between 2.3-2.6.',
        formula: 'Total Points ÷ Matches Played'
    },
    'xg': {
        title: 'Expected Goals',
        subtitle: 'Chance Quality Metric',
        description: 'Measures the quality of scoring chances based on multiple factors: distance from goal, angle, body part used, type of assist, and defensive pressure. Shows how many goals a team should have scored given their chances created.',
        example: 'A team with 2.5 xG means they created chances worth 2.5 goals on average. If they scored 3 goals, they overperformed; if they scored 1, they underperformed.',
        formula: '∑(shot probability based on location & context)'
    },
    'gd': {
        title: 'Goal Difference',
        subtitle: 'Goals Scored - Goals Conceded',
        description: 'The difference between goals scored and goals conceded. Shows overall team dominance, attacking prowess, and defensive stability. A key indicator of team performance and often correlates strongly with league position.',
        example: 'A GD of +15 means the team has scored 15 more goals than they have conceded. Title-winning teams typically have GD of +40 or higher.',
        formula: 'Goals For - Goals Against'
    },
    'form': {
        title: 'Recent Form',
        subtitle: 'Last 5-10 Matches Performance',
        description: 'Team performance in recent matches, shown as results sequence (W=Win, D=Draw, L=Loss). Considers momentum, injuries, tactical changes, and psychological factors that affect short-term performance.',
        example: 'WWLWD means: Win, Win, Loss, Win, Draw in their last 5 matches. Teams in "hot form" (WWWWW) often outperform their season averages.',
        formula: 'Results sequence with recency weighting'
    },
    'btts': {
        title: 'Both Teams To Score',
        subtitle: 'Attack vs Defense Probability',
        description: 'Probability that both teams will score at least one goal in the match. Based on teams\' offensive capabilities and defensive vulnerabilities, historical BTTS rates, and recent trends.',
        example: 'BTTS probability of 65% means there\'s a strong chance both teams will find the net, suggesting an open, attacking game.',
        formula: 'Offensive strength × Defensive weakness × Historical rate'
    },
    'over25': {
        title: 'Over 2.5 Goals',
        subtitle: 'High-Scoring Match Probability',
        description: 'Probability that the match will have 3 or more total goals. Based on teams\' attacking styles, defensive records, tempo of play, and historical goal averages.',
        example: 'Over 2.5 probability of 72% suggests a high-scoring game is likely, ideal for goals-based betting markets.',
        formula: 'Average goals per match × Attack/Defense ratio'
    }
};

// Initialize metric explanation system
function initMetricSystem() {
    // Create metric modal if it doesn't exist
    if (!document.getElementById('metricModal')) {
        metricModal = document.createElement('div');
        metricModal.id = 'metricModal';
        metricModal.className = 'metric-modal';
        metricModal.innerHTML = `
            <div class="modal-content">
                <span class="close-modal">&times;</span>
                <h3 id="metricTitle"></h3>
                <div id="metricSubtitle" class="metric-subtitle"></div>
                <p id="metricDescription"></p>
                <div class="metric-example">
                    <h4>Example</h4>
                    <p id="metricExample"></p>
                </div>
                <div class="modal-footer">
                    <span class="brand">SCORE_PULSE Analytics</span>
                    <button class="got-it" onclick="hideMetricExplanation()">Got it</button>
                </div>
            </div>
        `;
        document.body.appendChild(metricModal);
        
        // Add close event
        const closeBtn = metricModal.querySelector('.close-modal');
        closeBtn.addEventListener('click', hideMetricExplanation);
        
        // Close on background click
        metricModal.addEventListener('click', function(e) {
            if (e.target === this) {
                hideMetricExplanation();
            }
        });
    } else {
        metricModal = document.getElementById('metricModal');
    }
    
    // Make metric explanations globally accessible
    window.metricExplanations = metricExplanations;
    window.showMetricExplanation = showMetricExplanation;
    window.hideMetricExplanation = hideMetricExplanation;
    
    // Add click handlers to all metric elements
    document.addEventListener('click', function(e) {
        const metricElement = e.target.closest('[data-metric]');
        if (metricElement) {
            const metricKey = metricElement.getAttribute('data-metric');
            showMetricExplanation(metricKey);
        }
    });
    
    console.log('Metric explanation system initialized');
}

// Show metric explanation
function showMetricExplanation(metricKey) {
    const explanation = metricExplanations[metricKey];
    if (!explanation) {
        console.warn(`No explanation found for metric: ${metricKey}`);
        return;
    }
    
    // Update modal content
    document.getElementById('metricTitle').textContent = explanation.title;
    document.getElementById('metricSubtitle').textContent = explanation.subtitle;
    document.getElementById('metricDescription').textContent = explanation.description;
    document.getElementById('metricExample').textContent = explanation.example;
    
    // Show modal with animation
    metricModal.classList.add('active');
    document.body.style.overflow = 'hidden'; // Prevent scrolling
    
    // Play success sound (optional)
    playSound('info');
}

// Hide metric explanation
function hideMetricExplanation() {
    metricModal.classList.remove('active');
    document.body.style.overflow = ''; // Restore scrolling
    
    // Play close sound (optional)
    playSound('close');
}

// Sound effects (optional)
function playSound(type) {
    if (typeof window.audioEnabled === 'undefined' || !window.audioEnabled) return;
    
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        if (type === 'info') {
            oscillator.frequency.setValueAtTime(523.25, audioContext.currentTime); // C5
        } else if (type === 'close') {
            oscillator.frequency.setValueAtTime(392.00, audioContext.currentTime); // G4
        }
        
        gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
        
        oscillator.start();
        oscillator.stop(audioContext.currentTime + 0.5);
    } catch (e) {
        console.log('Audio not supported');
    }
}

// --- PREDICTION LOADING STATE ---
function showLoader() {
    const btn = document.querySelector('button[type="submit"]');
    if (btn) {
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `
            <div style="display: inline-flex; align-items: center; gap: 0.5rem;">
                <svg class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>Analyzing Match Data...</span>
            </div>
        `;
        
        // Add pulsing animation
        btn.classList.add('pulse');
        
        // Safety timeout in case server hangs (re-enable after 20s)
        setTimeout(() => {
            btn.disabled = false;
            btn.innerHTML = originalText;
            btn.classList.remove('pulse');
        }, 20000);
    }
}

// Enhanced form submission with analytics
function enhanceFormSubmission() {
    const form = document.querySelector('form');
    if (form) {
        form.addEventListener('submit', function(e) {
            const homeTeam = document.getElementById('home_team')?.value;
            const awayTeam = document.getElementById('away_team')?.value;
            
            if (!homeTeam || !awayTeam) {
                e.preventDefault();
                alert('Please select both teams before running simulation.');
                return false;
            }
            
            // Track prediction attempt
            if (typeof gtag !== 'undefined') {
                gtag('event', 'prediction_attempt', {
                    'home_team': homeTeam,
                    'away_team': awayTeam,
                    'event_category': 'predictions'
                });
            }
            
            showLoader();
            return true;
        });
    }
}

// --- M-PESA PAYMENT MODAL LOGIC ---
function openPaymentModal(plan, amount) {
    currentAmount = amount;
    currentPlan = plan;
    
    const modal = document.getElementById('paymentModal');
    const amountLabel = document.getElementById('payAmount');
    
    if (modal && amountLabel) {
        amountLabel.innerText = "KES " + amount;
        modal.classList.remove('hidden');
        
        // Add modal animation
        setTimeout(() => {
            modal.style.opacity = '1';
        }, 10);
    } else {
        alert("Payment system initializing... please refresh.");
    }
}

function closePaymentModal() {
    const modal = document.getElementById('paymentModal');
    if (modal) {
        modal.style.opacity = '0';
        setTimeout(() => {
            modal.classList.add('hidden');
        }, 300);
    }
}

async function triggerMpesa() {
    const phoneInput = document.getElementById('mpesaPhone');
    const statusDiv = document.getElementById('paymentStatus');
    const btn = document.getElementById('payBtn');
    
    const phone = phoneInput.value.trim();
    
    // Enhanced validation (Kenyan number format)
    const phoneRegex = /^(?:254|\+254|0)?(7(?:(?:[129][0-9])|(?:0[0-8])|(?:4[0-1]))[0-9]{6})$/;
    if (!phoneRegex.test(phone)) {
        statusDiv.innerHTML = `
            <div class="flex items-center gap-2 text-red-500">
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
                </svg>
                <span>Invalid Phone Number. Use format: 0712345678</span>
            </div>
        `;
        statusDiv.className = "text-red-500 text-sm font-bold mt-2";
        statusDiv.classList.remove('hidden');
        phoneInput.focus();
        return;
    }

    // UI Update
    btn.disabled = true;
    btn.innerHTML = `
        <div class="flex items-center gap-2">
            <svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>Sending Payment Request...</span>
        </div>
    `;
    statusDiv.classList.add('hidden');

    try {
        const formData = new FormData();
        formData.append('phone_number', phone);
        formData.append('amount', currentAmount);
        formData.append('plan', currentPlan);

        const response = await fetch('/mpesa/stkpush', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            statusDiv.innerHTML = `
                <div class="flex items-center gap-2 text-green-500">
                    <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                    </svg>
                    <span>Request Sent! Check your phone to enter PIN.</span>
                </div>
            `;
            statusDiv.className = "text-green-500 text-sm font-bold mt-2";
            statusDiv.classList.remove('hidden');
            
            // Show countdown
            let countdown = 5;
            const countdownInterval = setInterval(() => {
                statusDiv.innerHTML = `
                    <div class="flex items-center gap-2 text-green-500">
                        <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                        </svg>
                        <span>Payment successful! Redirecting in ${countdown}...</span>
                    </div>
                `;
                countdown--;
                
                if (countdown < 0) {
                    clearInterval(countdownInterval);
                    window.location.href = "/profile";
                }
            }, 1000);
        } else {
            throw new Error(result.error || "Payment Failed");
        }

    } catch (error) {
        console.error('Payment error:', error);
        statusDiv.innerHTML = `
            <div class="flex items-center gap-2 text-red-500">
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
                </svg>
                <span>Error: ${error.message}</span>
            </div>
        `;
        statusDiv.className = "text-red-500 text-sm font-bold mt-2";
        statusDiv.classList.remove('hidden');
        btn.disabled = false;
        btn.innerHTML = "Pay Now";
    }
}

// --- UTILITY FUNCTIONS ---
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!');
    }).catch(err => {
        console.error('Failed to copy:', err);
    });
}

function showToast(message, type = 'info') {
    // Create toast if it doesn't exist
    let toast = document.getElementById('globalToast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'globalToast';
        toast.className = 'fixed bottom-4 right-4 z-50 hidden';
        document.body.appendChild(toast);
    }
    
    const typeClasses = {
        'info': 'bg-blue-600',
        'success': 'bg-green-600',
        'warning': 'bg-yellow-600',
        'error': 'bg-red-600'
    };
    
    toast.innerHTML = `
        <div class="${typeClasses[type]} text-white px-6 py-3 rounded-lg shadow-lg flex items-center gap-3">
            <span>${message}</span>
            <button onclick="this.parentElement.parentElement.classList.add('hidden')" class="text-white hover:text-gray-200">
                &times;
            </button>
        </div>
    `;
    
    toast.classList.remove('hidden');
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}

// --- INITIALIZATION ---
document.addEventListener("DOMContentLoaded", function() {
    console.log('SCORE_PULSE Analytics System Initializing...');
    
    // Initialize metric explanation system
    initMetricSystem();
    
    // Initialize form submission handling
    enhanceFormSubmission();
    
    // Initialize payment system if elements exist
    const paymentModal = document.getElementById('paymentModal');
    if (paymentModal) {
        // Add click outside to close
        paymentModal.addEventListener('click', function(e) {
            if (e.target === this) {
                closePaymentModal();
            }
        });
        
        // Add escape key to close
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && !paymentModal.classList.contains('hidden')) {
                closePaymentModal();
            }
        });
    }
    
    // Add fade-in animations to content
    const contentElements = document.querySelectorAll('.reveal');
    contentElements.forEach(el => {
        if (!el.classList.contains('active')) {
            el.classList.add('fade-in');
        }
    });
    
    console.log('SCORE_PULSE Analytics System Ready');
});

// Make functions globally available
window.openPaymentModal = openPaymentModal;
window.closePaymentModal = closePaymentModal;
window.triggerMpesa = triggerMpesa;
window.copyToClipboard = copyToClipboard;
window.showToast = showToast;