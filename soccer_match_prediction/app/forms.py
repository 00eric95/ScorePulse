# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField, TextAreaField, FloatField, IntegerField, DateField, HiddenField, DecimalField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional, NumberRange, Regexp
from app.models import User, Team, League, Match
from datetime import date, datetime
import json

class RegistrationForm(FlaskForm):
    username = StringField('Username', 
                           validators=[
                               DataRequired(), 
                               Length(min=2, max=20),
                               Regexp(
                                   r'^[A-Za-z0-9][A-Za-z0-9 ._-]*$', 
                                    message='"Username may contain letters, numbers, spaces, dots underscores or hyphens"')     
                           ],
                           render_kw={
                               "placeholder": "Choose a unique username",
                               "class": "form-control"
                           })
    
    email = StringField('Email', 
                        validators=[
                            DataRequired(), 
                            Email(), 
                            Length(max=120)
                        ],
                        render_kw={
                            "placeholder": "Enter your email",
                            "type": "email",
                            "class": "form-control"
                        })

        
    password = PasswordField('Password', 
                            validators=[
                                DataRequired(),
                                Length(min=8, message='Password must be at least 8 characters'),
                                Regexp(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+= \-\[\]{}|]).{8,}$',
                                      message='Password must contain at least one uppercase letter, one lowercase letter, one number and one special character')
                            ],
                            render_kw={
                                "placeholder": "Create a strong password",
                                "class": "form-control"
                            })
    
    confirm_password = PasswordField('Confirm Password', 
                                     validators=[DataRequired(), EqualTo('password')],
                                     render_kw={
                                         "placeholder": "Re-enter your password",
                                         "class": "form-control"
                                     })
    
    #terms = BooleanField('Terms', validators=[DataRequired()])
    
    referral_code = StringField('Referral Code (Optional)',
                               validators=[Optional(), Length(max=20)],
                               render_kw={
                                   "placeholder": "Enter referral code if any",
                                   "class": "form-control"
                               })
    
    coupon_code = StringField('Coupon Code (Optional)',
                             validators=[Optional(), Length(max=20)],
                             render_kw={
                                 "placeholder": "Enter coupon code for bonus credits",
                                 "class": "form-control"
                             })
    
    terms = BooleanField('I agree to the Terms and Privacy Policy',
                              validators=[DataRequired(message="You must accept the terms to register.")]
                              )
    
    subscribe_newsletter = BooleanField('Subscribe to newsletter (Get betting tips & updates)',
                                       default=True)
    
    submit = SubmitField('Sign Up', 
                        render_kw={"class": "btn btn-primary btn-lg w-100"})

    def validate_username(self, username):
        # Check for offensive/inappropriate usernames
        offensive_terms = ['admin', 'root', 'moderator', 'system', 'support', 'owner']
        if username.data.lower() in offensive_terms:
            raise ValidationError('This username is not allowed. Please choose another.')
        
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        # Check email format more thoroughly
        import re
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email.data):
            raise ValidationError('Please enter a valid email address.')
        
        # Check disposable email domains
        disposable_domains = ['tempmail.com', 'throwaway.com', 'fake.com', 'guerrillamail.com']
        domain = email.data.split('@')[-1].lower()
        if domain in disposable_domains:
            raise ValidationError('Disposable email addresses are not allowed.')
        
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is already in use. Please log in or use a different email.')

class LoginForm(FlaskForm):
    email = StringField('Email / Username', 
                        validators=[DataRequired()],
                        render_kw={
                            "placeholder": "Enter your email or username",
                            "class": "form-control"
                        })
    
    password = PasswordField('Password', 
                            validators=[DataRequired()],
                            render_kw={
                                "placeholder": "Enter your password",
                                "class": "form-control"
                            })
    
    remember = BooleanField('Remember Me',
                           render_kw={"class": "form-check-input"})
    
    submit = SubmitField('Login',
                        render_kw={"class": "btn btn-primary btn-lg w-100"})

class PredictForm(FlaskForm):
    # Dynamic choices will be populated in routes
    home_team = SelectField('Home Team', 
                           validators=[DataRequired()], 
                           choices=[('', 'Select Home Team')],
                           render_kw={
                               "class": "form-control select2",
                               "id": "home_team_select",
                               "data-placeholder": "Type to search teams..."
                           })
    
    away_team = SelectField('Away Team', 
                           validators=[DataRequired()], 
                           choices=[('', 'Select Away Team')],
                           render_kw={
                               "class": "form-control select2",
                               "id": "away_team_select",
                               "data-placeholder": "Type to search teams..."
                           })
    
    match_date = DateField('Match Date',
                          format='%Y-%m-%d',
                          default=datetime.now(),
                          render_kw={
                              "class": "form-control",
                              "id": "match_date"
                          })
    
    user_prediction = SelectField('Your Prediction (Optional)', 
                                  choices=[
                                      ('None', 'Skip Saving (Just Analyze)'), 
                                      ('H', '🏠 Home Win'), 
                                      ('D', '⚖ Draw'), 
                                      ('A', '✈ Away Win')
                                  ],
                                  default='None',
                                  render_kw={
                                      "class": "form-control",
                                      "id": "user_prediction_select"
                                  })
    
    analysis_depth = SelectField('Analysis Depth',
                                choices=[
                                    ('basic', 'Basic Analysis (Fast)'),
                                    ('standard', 'Standard Analysis (Recommended)'),
                                    ('advanced', 'Advanced Analysis (Detailed)')
                                ],
                                default='standard',
                                render_kw={
                                    "class": "form-control",
                                    "id": "analysis_depth"
                                })
    
    store_prediction = BooleanField('Store this prediction for learning',
                                   default=True,
                                   render_kw={"class": "form-check-input"})
    
    submit = SubmitField('Analyze Match 🚀',
                        render_kw={
                            "class": "btn btn-success btn-lg w-100",
                            "id": "analyze_button"
                        })

class ResultSubmissionForm(FlaskForm):
    """Form for submitting actual match results"""
    match_id = StringField('Match ID',
                          validators=[DataRequired(), Length(max=50)],
                          render_kw={
                              "placeholder": "Match ID from prediction",
                              "class": "form-control"
                          })
    
    home_team = StringField('Home Team',
                           validators=[DataRequired(), Length(max=100)],
                           render_kw={
                               "placeholder": "Home team name",
                               "class": "form-control"
                           })
    
    away_team = StringField('Away Team',
                           validators=[DataRequired(), Length(max=100)],
                           render_kw={
                               "placeholder": "Away team name",
                               "class": "form-control"
                           })
    
    match_date = DateField('Match Date',
                          format='%Y-%m-%d',
                          validators=[DataRequired()],
                          render_kw={"class": "form-control"})
    
    home_goals = IntegerField('Home Goals',
                             validators=[DataRequired(), NumberRange(min=0)],
                             render_kw={
                                 "placeholder": "Home team goals",
                                 "class": "form-control",
                                 "min": "0"
                             })
    
    away_goals = IntegerField('Away Goals',
                             validators=[DataRequired(), NumberRange(min=0)],
                             render_kw={
                                 "placeholder": "Away team goals",
                                 "class": "form-control",
                                 "min": "0"
                             })
    
    submit = SubmitField('Submit Result',
                        render_kw={"class": "btn btn-primary"})

class BatchResultForm(FlaskForm):
    """Form for submitting multiple results via JSON"""
    results_json = TextAreaField('Results JSON',
                                validators=[DataRequired()],
                                render_kw={
                                    "placeholder": 'Paste JSON array: [{"match_id": "...", "home_team": "...", ...}]',
                                    "class": "form-control",
                                    "rows": 10
                                })
    
    submit = SubmitField('Submit Batch Results',
                        render_kw={"class": "btn btn-warning"})

class PredictionStatsForm(FlaskForm):
    """Form for viewing prediction statistics"""
    days_back = SelectField('Time Period',
                           choices=[
                               (7, 'Last 7 days'),
                               (30, 'Last 30 days'),
                               (90, 'Last 90 days'),
                               (180, 'Last 6 months'),
                               (365, 'Last year'),
                               (0, 'All time')
                           ],
                           default=30,
                           coerce=int,
                           render_kw={"class": "form-control"})
    
    show_unprocessed = BooleanField('Show unprocessed results only',
                                   default=False,
                                   render_kw={"class": "form-check-input"})
    
    submit = SubmitField('View Statistics',
                        render_kw={"class": "btn btn-info"})

class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', 
                        validators=[DataRequired(), Email()],
                        render_kw={
                            "placeholder": "Enter your email address",
                            "class": "form-control"
                        })
    
    submit = SubmitField('Send Reset Instructions',
                        render_kw={"class": "btn btn-primary w-100"})
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if not user:
            raise ValidationError('No account found with this email address.')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', 
                            validators=[
                                DataRequired(),
                                Length(min=8, message='Password must be at least 8 characters'),
                                Regexp(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+= \-\[\]{}|]).{8,}$',
                                      message='Password must contain at least one uppercase letter, one lowercase letter, one number and one special character')
                            ],
                            render_kw={
                                "placeholder": "Enter new password",
                                "class": "form-control"
                            })
    
    confirm_password = PasswordField('Confirm New Password', 
                                     validators=[DataRequired(), EqualTo('password')],
                                     render_kw={
                                         "placeholder": "Confirm new password",
                                         "class": "form-control"
                                     })
    
    submit = SubmitField('Reset Password',
                        render_kw={"class": "btn btn-primary w-100"})

class CouponForm(FlaskForm):
    coupon_code = StringField('Coupon Code',
                             validators=[
                                 DataRequired(),
                                 Length(max=20),
                                 Regexp('^[A-Z0-9-]+$', message='Coupon code must contain only uppercase letters, numbers, and hyphens')
                             ],
                             render_kw={
                                 "placeholder": "ENTER COUPON CODE",
                                 "class": "form-control text-uppercase",
                                 "style": "font-weight: bold; letter-spacing: 1px;"
                             })
    
    submit = SubmitField('Apply Coupon 🎁',
                        render_kw={"class": "btn btn-warning w-100"})

class PaymentForm(FlaskForm):
    amount = SelectField('Select Package',
                        choices=[
                            ('5', '5 Credits - $5'),
                            ('10', '10 Credits - $9 (Save 10%)'),
                            ('25', '25 Credits - $20 (Save 20%)'),
                            ('50', '50 Credits - $35 (Save 30%)'),
                            ('100', '100 Credits - $60 (Save 40%)'),
                            ('unlimited', 'Unlimited (Gold Tier) - $99/month')
                        ],
                        validators=[DataRequired()],
                        render_kw={"class": "form-control"})
    
    payment_method = SelectField('Payment Method',
                                choices=[
                                    ('mpesa', 'M-Pesa (Kenya)'),
                                    ('stripe', 'Credit/Debit Card (Stripe)'),
                                    ('paypal', 'PayPal'),
                                    ('crypto', 'Cryptocurrency')
                                ],
                                validators=[DataRequired()],
                                render_kw={"class": "form-control"})
    
    phone_number = StringField('Phone Number (M-Pesa Only)',
                              validators=[Optional(), Length(min=10, max=15)],
                              render_kw={
                                  "placeholder": "e.g. 254712345678",
                                  "class": "form-control",
                                  "id": "phone_number_field"
                              })
    
    coupon_code = StringField('Coupon Code (Optional)',
                             validators=[Optional(), Length(max=20)],
                             render_kw={
                                 "placeholder": "Apply coupon for discount",
                                 "class": "form-control"
                             })
    
    submit = SubmitField('Proceed to Payment',
                        render_kw={"class": "btn btn-success btn-lg w-100"})

class ProfileUpdateForm(FlaskForm):
    username = StringField('Username',
                          validators=[
                              DataRequired(),
                              Length(min=2, max=20),
                              Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0,
                                     'Username must start with a letter and contain only letters, numbers, dots or underscores')
                          ],
                          render_kw={"class": "form-control"})
    
    email = StringField('Email',
                       validators=[DataRequired(), Email()],
                       render_kw={"class": "form-control", "readonly": True})
    
    full_name = StringField('Full Name (Optional)',
                           validators=[Optional(), Length(max=50)],
                           render_kw={
                               "placeholder": "Enter your full name",
                               "class": "form-control"
                           })
    
    phone = StringField('Phone Number (Optional)',
                       validators=[Optional(), Length(max=20)],
                       render_kw={
                           "placeholder": "e.g. +1234567890",
                           "class": "form-control"
                       })
    
    country = SelectField('Country (Optional)',
                         choices=[
                             ('', 'Select Country'),
                             ('KE', 'Kenya'),
                             ('US', 'United States'),
                             ('UK', 'United Kingdom'),
                             ('NG', 'Nigeria'),
                             ('GH', 'Ghana'),
                             ('ZA', 'South Africa'),
                             ('CA', 'Canada'),
                             ('AU', 'Australia'),
                             ('IN', 'India'),
                             ('OTHER', 'Other')
                         ],
                         validators=[Optional()],
                         render_kw={"class": "form-control"})
    
    bio = TextAreaField('Bio (Optional)',
                       validators=[Optional(), Length(max=500)],
                       render_kw={
                           "placeholder": "Tell us about yourself...",
                           "class": "form-control",
                           "rows": 3
                       })
    
    email_notifications = BooleanField('Receive Email Notifications',
                                      default=True,
                                      render_kw={"class": "form-check-input"})
    
    sms_notifications = BooleanField('Receive SMS Notifications (Matches & Predictions)',
                                    default=False,
                                    render_kw={"class": "form-check-input"})
    
    weekly_report = BooleanField('Receive Weekly Performance Report',
                                default=True,
                                render_kw={"class": "form-check-input"})
    
    submit = SubmitField('Update Profile',
                        render_kw={"class": "btn btn-primary"})

class PasswordChangeForm(FlaskForm):
    current_password = PasswordField('Current Password',
                                    validators=[DataRequired()],
                                    render_kw={
                                        "placeholder": "Enter current password",
                                        "class": "form-control"
                                    })
    
    new_password = PasswordField('New Password',
                                validators=[
                                    DataRequired(),
                                    Length(min=8, message='Password must be at least 8 characters'),
                                    Regexp(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+= \-\[\]{}|]).{8,}$',
                                          message='Password must contain at least one uppercase letter, one lowercase letter, one number and one special character')
                                ],
                                render_kw={
                                    "placeholder": "Enter new password",
                                    "class": "form-control"
                                })
    
    confirm_new_password = PasswordField('Confirm New Password',
                                        validators=[DataRequired(), EqualTo('new_password')],
                                        render_kw={
                                            "placeholder": "Confirm new password",
                                            "class": "form-control"
                                        })
    
    submit = SubmitField('Change Password',
                        render_kw={"class": "btn btn-warning"})

class AdminCouponForm(FlaskForm):
    code = StringField('Coupon Code',
                      validators=[
                          DataRequired(),
                          Length(max=20),
                          Regexp('^[A-Z0-9-]+$', message='Coupon code must contain only uppercase letters, numbers, and hyphens')
                      ],
                      render_kw={
                          "placeholder": "e.g. WELCOME20",
                          "class": "form-control text-uppercase"
                      })
    
    discount_type = SelectField('Discount Type',
                               choices=[
                                   ('percentage', 'Percentage Discount'),
                                   ('fixed', 'Fixed Amount Discount'),
                                   ('credits', 'Credits Only')
                               ],
                               default='percentage',
                               validators=[DataRequired()],
                               render_kw={"class": "form-control"})
    
    discount_value = FloatField('Discount Value',
                               validators=[
                                   DataRequired(),
                                   NumberRange(min=0)
                               ],
                               render_kw={
                                   "placeholder": "e.g. 20 for 20% or $20",
                                   "class": "form-control"
                               })
    
    credits_awarded = IntegerField('Credits Awarded',
                                  validators=[
                                      DataRequired(),
                                      NumberRange(min=0, max=1000)
                                  ],
                                  render_kw={
                                      "placeholder": "Number of credits to award",
                                      "class": "form-control"
                                  })
    
    upgrade_tier = SelectField('Upgrade Tier (Optional)',
                              choices=[
                                  ('', 'No Tier Upgrade'),
                                  ('free', 'Free Tier'),
                                  ('silver', 'Silver Tier'),
                                  ('gold', 'Gold Tier'),
                                  ('platinum', 'Platinum Tier')
                              ],
                              validators=[Optional()],
                              render_kw={"class": "form-control"})
    
    expiry_date = DateField('Expiry Date (Optional)',
                           format='%Y-%m-%d',
                           validators=[Optional()],
                           render_kw={
                               "class": "form-control",
                               "min": date.today().isoformat()
                           })
    
    max_uses = IntegerField('Maximum Uses (0 = Unlimited)',
                           validators=[Optional(), NumberRange(min=0)],
                           default=0,
                           render_kw={
                               "placeholder": "0 for unlimited uses",
                               "class": "form-control"
                           })
    
    description = TextAreaField('Description (Optional)',
                               validators=[Optional(), Length(max=200)],
                               render_kw={
                                   "placeholder": "Describe this coupon code...",
                                   "class": "form-control",
                                   "rows": 2
                               })
    
    submit = SubmitField('Create Coupon',
                        render_kw={"class": "btn btn-success"})

class ContactForm(FlaskForm):
    name = StringField('Your Name',
                      validators=[DataRequired(), Length(max=50)],
                      render_kw={
                          "placeholder": "Enter your name",
                          "class": "form-control"
                      })
    
    email = StringField('Email',
                       validators=[DataRequired(), Email()],
                       render_kw={
                           "placeholder": "Enter your email",
                           "class": "form-control"
                       })
    
    subject = SelectField('Subject',
                         choices=[
                             ('general', 'General Inquiry'),
                             ('technical', 'Technical Support'),
                             ('billing', 'Billing/Payment'),
                             ('suggestion', 'Feature Suggestion'),
                             ('bug', 'Bug Report'),
                             ('partnership', 'Partnership/API')
                         ],
                         validators=[DataRequired()],
                         render_kw={"class": "form-control"})
    
    message = TextAreaField('Message',
                          validators=[DataRequired(), Length(min=10, max=1000)],
                          render_kw={
                              "placeholder": "Type your message here...",
                              "class": "form-control",
                              "rows": 5
                          })
    
    submit = SubmitField('Send Message',
                        render_kw={"class": "btn btn-primary"})

class FeedbackForm(FlaskForm):
    feedback_type = SelectField('Type', 
                               choices=[('bug', 'Bug Report'), 
                                        ('suggestion', 'Suggestion'), 
                                        ('question', 'General Question')], 
                               validators=[DataRequired()],
                               render_kw={"class": "form-control"})
    subject = StringField('Subject', 
                         validators=[DataRequired(), Length(max=100)],
                         render_kw={"class": "form-control", "placeholder": "Brief summary"})
    message = TextAreaField('Message', 
                           validators=[DataRequired(), Length(min=10)],
                           render_kw={"class": "form-control", "rows": 5, "placeholder": "Describe your feedback in detail..."})
    priority = SelectField('Priority', 
                          choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], 
                          default='medium',
                          render_kw={"class": "form-control"})
    submit = SubmitField('Submit Feedback',
                        render_kw={"class": "btn btn-primary w-100"})

class NewsletterForm(FlaskForm):
    email = StringField('Email Address',
                       validators=[DataRequired(), Email()],
                       render_kw={
                           "placeholder": "Enter your email to subscribe",
                           "class": "form-control"
                       })
    
    frequency = SelectField('Newsletter Frequency',
                           choices=[
                               ('weekly', 'Weekly Digest'),
                               ('biweekly', 'Bi-weekly Updates'),
                               ('monthly', 'Monthly Roundup')
                           ],
                           default='weekly',
                           render_kw={"class": "form-control"})
    
    interests = SelectField('Areas of Interest',
                           choices=[
                               ('all', 'All Football Leagues'),
                               ('premier', 'Premier League Only'),
                               ('champions', 'Champions League/Europa'),
                               ('international', 'International Matches'),
                               ('predictions', 'Betting Tips & Predictions'),
                               ('stats', 'Statistics & Analytics')
                           ],
                           default='all',
                           render_kw={"class": "form-control"})
    
    submit = SubmitField('Subscribe Now',
                        render_kw={"class": "btn btn-success"})

class MpesaPaymentForm(FlaskForm):
    phone_number = StringField('Phone Number',
                              validators=[
                                  DataRequired(),
                                  Length(min=10, max=15),
                                  Regexp('^(254|0)[0-9]{9}$', message='Enter a valid Kenyan phone number (e.g., 254712345678 or 0712345678)')
                              ],
                              render_kw={
                                  "placeholder": "254712345678 or 0712345678",
                                  "class": "form-control",
                                  "id": "mpesa_phone"
                              })
    
    amount = SelectField('Select Amount',
                        choices=[
                            ('100', 'KES 100 (Test)'),
                            ('500', 'KES 500 (5 Credits)'),
                            ('1000', 'KES 1,000 (12 Credits)'),
                            ('2000', 'KES 2,000 (25 Credits)'),
                            ('5000', 'KES 5,000 (70 Credits)')
                        ],
                        validators=[DataRequired()],
                        render_kw={
                            "class": "form-control",
                            "id": "mpesa_amount"
                        })
    
    coupon_code = StringField('Coupon Code (Optional)',
                             validators=[Optional(), Length(max=20)],
                             render_kw={
                                 "placeholder": "Enter coupon code if any",
                                 "class": "form-control"
                             })
    
    submit = SubmitField('Initiate M-Pesa Payment',
                        render_kw={"class": "btn btn-success btn-lg w-100"})
    
    def validate_phone_number(self, phone_number):
        # Ensure phone number is valid Kenyan format
        phone = phone_number.data.strip()
        if phone.startswith('0'):
            phone = '254' + phone[1:]
            self.phone_number.data = phone

class TeamComparisonForm(FlaskForm):
    team1 = SelectField('First Team',
                       validators=[DataRequired()],
                       choices=[('', 'Select First Team')],
                       render_kw={
                           "class": "form-control select2",
                           "id": "team1_select",
                           "data-placeholder": "Type to search teams..."
                       })
    
    team2 = SelectField('Second Team',
                       validators=[DataRequired()],
                       choices=[('', 'Select Second Team')],
                       render_kw={
                           "class": "form-control select2",
                           "id": "team2_select",
                           "data-placeholder": "Type to search teams..."
                       })
    
    comparison_type = SelectField('Comparison Type',
                                 choices=[
                                     ('h2h', 'Head-to-Head History'),
                                     ('stats', 'Statistical Comparison'),
                                     ('form', 'Current Form Analysis'),
                                     ('detailed', 'Detailed Team Report')
                                 ],
                                 default='h2h',
                                 validators=[DataRequired()],
                                 render_kw={"class": "form-control"})
    
    submit = SubmitField('Compare Teams 🔍',
                        render_kw={"class": "btn btn-info w-100"})

class CustomPredictionForm(FlaskForm):
    home_team = StringField('Home Team', 
                           validators=[DataRequired()], 
                           render_kw={"class": "form-control"})
    
    away_team = StringField('Away Team', 
                           validators=[DataRequired()], 
                           render_kw={"class": "form-control"})
    
    confidence_threshold = FloatField('Confidence Threshold (%)', 
                                     default=70.0, 
                                     validators=[DataRequired()], 
                                     render_kw={"class": "form-control"})
    
    include_head_to_head = BooleanField('Include H2H History', 
                                       default=True)
    
    include_form = BooleanField('Include Current Form', 
                               default=True)
    
    include_injuries = BooleanField('Include Injury Data', 
                                   default=False)
    
    betting_strategy = SelectField('Strategy', 
                                  choices=[('conservative', 'Conservative'), 
                                           ('balanced', 'Balanced'), 
                                           ('aggressive', 'Aggressive')], 
                                  default='balanced',
                                  render_kw={"class": "form-control"})
    
    risk_level = SelectField('Risk Level', 
                            choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], 
                            default='medium',
                            render_kw={"class": "form-control"})
    
    submit = SubmitField('Generate Advanced Prediction', 
                        render_kw={"class": "btn btn-success w-100"})

class AdvancedSettingsForm(FlaskForm):
    """Form for advanced prediction settings"""
    # Team selection
    home_team = SelectField('Home Team', validators=[DataRequired()])
    away_team = SelectField('Away Team', validators=[DataRequired()])
    
    # Confidence settings
    confidence_threshold = IntegerField('Confidence Threshold', 
                                       validators=[DataRequired(), 
                                                   NumberRange(min=50, max=95)],
                                       default=75)
    
    # Data source toggles
    include_head_to_head = BooleanField('Include Head-to-Head', default=True)
    include_form = BooleanField('Include Recent Form', default=True)
    include_injuries = BooleanField('Include Injury Data', default=False)
    
    # Betting strategy
    betting_strategy = SelectField('Betting Strategy',
                                  choices=[
                                      ('value_betting', 'Value Betting'),
                                      ('conservative', 'Conservative'),
                                      ('aggressive', 'Aggressive'),
                                      ('arbitrage', 'Arbitrage'),
                                      ('accumulator', 'Accumulator'),
                                      ('hedging', 'Hedging'),
                                      ('in_play', 'In-Play')
                                  ],
                                  default='value_betting')
    
    # Risk level
    risk_level = SelectField('Risk Level',
                            choices=[
                                ('low', 'Low Risk'),
                                ('medium', 'Medium Risk'),
                                ('high', 'High Risk')
                            ],
                            default='medium')
    
    email_notifications = BooleanField('Email Notifications', default=True)
    
    submit = SubmitField('Run Advanced Analysis')

class OrchestrationForm(FlaskForm):
    """Form for running orchestration pipeline"""
    home_team = StringField('Home Team', 
                           validators=[DataRequired()])
    
    away_team = StringField('Away Team', 
                           validators=[DataRequired()])
    
    # Optional odds fields
    home_odds = DecimalField('Home Win Odds', 
                            places=2,
                            validators=[Optional(), NumberRange(min=1.0)])
    
    draw_odds = DecimalField('Draw Odds', 
                            places=2,
                            validators=[Optional(), NumberRange(min=1.0)])
    
    away_odds = DecimalField('Away Win Odds', 
                            places=2,
                            validators=[Optional(), NumberRange(min=1.0)])
    
    submit = SubmitField('Run Orchestration')

class AgentConfigurationForm(FlaskForm):
    """Form for configuring agents"""
    data_agent_path = StringField('Data Agent Path', 
                                 default='data/raw',
                                 validators=[DataRequired()])
    
    bankroll_initial_balance = FloatField('Initial Bankroll',
                                         default=1000.0,
                                         validators=[NumberRange(min=0)])
    
    bankroll_risk_appetite = StringField('Risk Appetite',
                                        default='half',
                                        validators=[DataRequired()])
    
    submit = SubmitField('Update Configuration')

class LearningProcessForm(FlaskForm):
    """Form for triggering learning processes"""
    process_type = SelectField('Process Type',
                              choices=[
                                  ('daily', 'Daily Results Processing'),
                                  ('hourly', 'Check New Results'),
                                  ('weekly', 'Weekly Analysis'),
                                  ('stats', 'Generate Statistics'),
                                  ('cleanup', 'Cleanup Old Data')
                              ],
                              validators=[DataRequired()],
                              render_kw={"class": "form-control"})
    
    limit = IntegerField('Limit (for batch processing)',
                        default=50,
                        validators=[Optional(), NumberRange(min=1, max=1000)],
                        render_kw={
                            "placeholder": "Number of records to process",
                            "class": "form-control"
                        })
    
    force = BooleanField('Force Processing',
                        default=False,
                        render_kw={"class": "form-check-input"})
    
    submit = SubmitField('Run Process',
                        render_kw={"class": "btn btn-warning"})

class PredictionReviewForm(FlaskForm):
    """Form for reviewing predictions vs results"""
    prediction_id = HiddenField('Prediction ID')
    
    match_id = StringField('Match ID',
                          render_kw={
                              "class": "form-control",
                              "readonly": True
                          })
    
    home_team = StringField('Home Team',
                           render_kw={
                               "class": "form-control",
                               "readonly": True
                           })
    
    away_team = StringField('Away Team',
                           render_kw={
                               "class": "form-control",
                               "readonly": True
                           })
    
    predicted_result = SelectField('Predicted Result',
                                  choices=[
                                      ('H', 'Home Win'),
                                      ('D', 'Draw'),
                                      ('A', 'Away Win')
                                  ],
                                  render_kw={
                                      "class": "form-control",
                                      "readonly": True
                                  })
    
    actual_home_goals = IntegerField('Actual Home Goals',
                                    validators=[DataRequired(), NumberRange(min=0)],
                                    render_kw={"class": "form-control"})
    
    actual_away_goals = IntegerField('Actual Away Goals',
                                    validators=[DataRequired(), NumberRange(min=0)],
                                    render_kw={"class": "form-control"})
    
    feedback_notes = TextAreaField('Feedback Notes (Optional)',
                                  validators=[Optional(), Length(max=500)],
                                  render_kw={
                                      "placeholder": "Add notes about this prediction...",
                                      "class": "form-control",
                                      "rows": 3
                                  })
    
    mark_processed = BooleanField('Mark as processed for learning',
                                 default=True,
                                 render_kw={"class": "form-check-input"})
    
    submit = SubmitField('Save Review',
                        render_kw={"class": "btn btn-primary"})

class DatabaseAdminForm(FlaskForm):
    """Form for database administration tasks"""
    action = SelectField('Action',
                        choices=[
                            ('backup', 'Backup Database'),
                            ('restore', 'Restore from Backup'),
                            ('cleanup', 'Cleanup Old Records'),
                            ('stats', 'View Database Statistics'),
                            ('optimize', 'Optimize Database')
                        ],
                        validators=[DataRequired()],
                        render_kw={"class": "form-control"})
    
    backup_file = StringField('Backup File (for restore)',
                             validators=[Optional()],
                             render_kw={
                                 "placeholder": "Enter backup filename",
                                 "class": "form-control"
                             })
    
    days_to_keep = IntegerField('Days to Keep (for cleanup)',
                               default=365,
                               validators=[Optional(), NumberRange(min=1)],
                               render_kw={
                                   "placeholder": "Days of data to keep",
                                   "class": "form-control"
                               })
    
    confirm = BooleanField('I confirm this action',
                          validators=[DataRequired()],
                          render_kw={"class": "form-check-input"})
    
    submit = SubmitField('Execute Action',
                        render_kw={"class": "btn btn-danger"})
    
class MatchOrchestrationForm(FlaskForm):
    """Form for running match orchestration via Pitch Commander"""
    home_team = StringField('Home Team', validators=[DataRequired()])
    away_team = StringField('Away Team', validators=[DataRequired()])
    
    # Market odds fields (optional)
    home_odds = FloatField('Home Win Odds', validators=[Optional(), NumberRange(min=1.01, max=50)])
    draw_odds = FloatField('Draw Odds', validators=[Optional(), NumberRange(min=1.01, max=50)])
    away_odds = FloatField('Away Win Odds', validators=[Optional(), NumberRange(min=1.01, max=50)])
    
    # Strategy options
    strategy = SelectField('Strategy', choices=[
        ('full', 'Full Orchestration (All Agents)'),
        ('prediction_only', 'Prediction Only'),
        ('with_betting', 'With Betting Strategy'),
        ('quick', 'Quick Analysis')
    ], default='full')
    
    submit = SubmitField('Run Orchestration')
    
class TeamAnalysisForm(FlaskForm):
    """Form for team analysis requests"""
    team_name = StringField('Team Name', validators=[
        DataRequired(),
        Length(min=2, max=100)
    ], render_kw={
        "placeholder": "Enter team name",
        "class": "form-control"
    })
    
    analysis_type = SelectField('Analysis Type', choices=[
        ('overall', 'Overall Performance'),
        ('form', 'Recent Form'),
        ('home', 'Home Record'),
        ('away', 'Away Record'),
        ('goals', 'Goal Analysis')
    ], default='overall', render_kw={
        "class": "form-control"
    })
    
    time_period = SelectField('Time Period', choices=[
        ('all', 'All Time'),
        ('season', 'Current Season'),
        ('year', 'Last Year'),
        ('custom', 'Custom Range')
    ], default='all', render_kw={
        "class": "form-control"
    })
    
    submit = SubmitField('Analyze Team', render_kw={
        "class": "btn btn-primary w-100"
    })

class HeadToHeadForm(FlaskForm):
    """Form for head-to-head comparison requests"""
    team1 = StringField('Team 1', validators=[
        DataRequired(),
        Length(min=2, max=100)
    ], render_kw={
        "placeholder": "Enter first team",
        "class": "form-control"
    })
    
    team2 = StringField('Team 2', validators=[
        DataRequired(),
        Length(min=2, max=100)
    ], render_kw={
        "placeholder": "Enter second team",
        "class": "form-control"
    })
    
    include_venue = BooleanField('Include Venue Analysis', default=True,
                               render_kw={"class": "form-check-input"})
    
    recency_weight = BooleanField('Weight Recent Matches', default=True,
                                 render_kw={"class": "form-check-input"})
    
    show_market = BooleanField('Show Market Insights', default=False,
                              render_kw={"class": "form-check-input"})
    
    submit = SubmitField('Compare Teams', render_kw={
        "class": "btn btn-info w-100"
    })

class MatchPredictionForm(FlaskForm):
    """Form for match prediction requests"""
    home_team = StringField('Home Team', validators=[
        DataRequired(),
        Length(min=2, max=100)
    ], render_kw={
        "placeholder": "Enter home team name",
        "class": "form-control"
    })
    
    away_team = StringField('Away Team', validators=[
        DataRequired(),
        Length(min=2, max=100)
    ], render_kw={
        "placeholder": "Enter away team name",
        "class": "form-control"
    })
    
    league = SelectField('League', choices=[
        ('', 'Any League'),
        ('Premier League', 'Premier League'),
        ('La Liga', 'La Liga'),
        ('Bundesliga', 'Bundesliga'),
        ('Serie A', 'Serie A'),
        ('Ligue 1', 'Ligue 1'),
        ('Champions League', 'Champions League'),
        ('Europa League', 'Europa League'),
        ('MLS', 'Major League Soccer'),
        ('EFL', 'English Football League')
    ], default='', render_kw={
        "class": "form-control"
    })
    
    include_form = BooleanField('Include Recent Form', default=True,
                              render_kw={"class": "form-check-input"})
    
    include_h2h = BooleanField('Include Head-to-Head', default=True,
                              render_kw={"class": "form-check-input"})
    
    include_odds = BooleanField('Include Market Odds', default=False,
                               render_kw={"class": "form-check-input"})
    
    submit = SubmitField('Predict Match', render_kw={
        "class": "btn btn-success w-100"
    })

class DataLoadForm(FlaskForm):
    """Form for loading new data"""
    data_source = SelectField('Data Source', choices=[
        ('kaggle', 'Kaggle Dataset'),
        ('file', 'Local CSV File'),
        ('api', 'API Source'),
        ('manual', 'Manual Entry')
    ], default='file', render_kw={
        "class": "form-control"
    })
    
    file_path = StringField('File Path', validators=[
        Optional(),
        Length(max=500)
    ], render_kw={
        "placeholder": "/path/to/data.csv",
        "class": "form-control"
    })
    
    start_date = DateField('Start Date', format='%Y-%m-%d',
                          validators=[Optional()],
                          render_kw={
                              "class": "form-control",
                              "placeholder": "YYYY-MM-DD"
                          })
    
    end_date = DateField('End Date', format='%Y-%m-%d',
                        validators=[Optional()],
                        render_kw={
                            "class": "form-control",
                            "placeholder": "YYYY-MM-DD"
                        })
    
    validation_level = SelectField('Validation Level', choices=[
        ('basic', 'Basic Validation'),
        ('strict', 'Strict Validation'),
        ('none', 'No Validation')
    ], default='basic', render_kw={
        "class": "form-control"
    })
    
    submit = SubmitField('Load Data', render_kw={
        "class": "btn btn-primary w-100"
    })

class FeatureGenerationForm(FlaskForm):
    """Form for feature generation requests"""
    feature_type = SelectField('Feature Type', choices=[
        ('basic', 'Basic Features'),
        ('advanced', 'Advanced Features'),
        ('all', 'All Features'),
        ('custom', 'Custom Features')
    ], default='advanced', render_kw={
        "class": "form-control"
    })
    
    include_elo = BooleanField('Include ELO Ratings', default=True,
                             render_kw={"class": "form-check-input"})
    
    include_form = BooleanField('Include Form Metrics', default=True,
                              render_kw={"class": "form-check-input"})
    
    include_market = BooleanField('Include Market Features', default=False,
                                 render_kw={"class": "form-check-input"})
    
    include_context = BooleanField('Include Context Features', default=True,
                                  render_kw={"class": "form-check-input"})
    
    window_sizes = StringField('Window Sizes (comma-separated)', 
                              default='3,5,10,20',
                              validators=[Optional()],
                              render_kw={
                                  "placeholder": "3,5,10,20",
                                  "class": "form-control"
                              })
    
    submit = SubmitField('Generate Features', render_kw={
        "class": "btn btn-warning w-100"
    })

class MatchImportForm(FlaskForm):
    """Form for importing matches from CSV"""
    csv_file = StringField('CSV File Path',
                          validators=[DataRequired(), Length(max=500)],
                          render_kw={
                              "placeholder": "/path/to/upcoming_matches.csv",
                              "class": "form-control"
                          })
    
    import_type = SelectField('Import Type',
                             choices=[
                                 ('append', 'Append New Matches Only'),
                                 ('replace', 'Replace All Matches'),
                                 ('update', 'Update Existing Matches')
                             ],
                             default='append',
                             render_kw={"class": "form-control"})
    
    validate_data = BooleanField('Validate Data Before Import',
                                default=True,
                                render_kw={"class": "form-check-input"})
    
    create_missing_teams = BooleanField('Create Missing Teams',
                                       default=True,
                                       render_kw={"class": "form-check-input"})
    
    create_missing_leagues = BooleanField('Create Missing Leagues',
                                         default=True,
                                         render_kw={"class": "form-check-input"})
    
    submit = SubmitField('Import Matches', render_kw={
        "class": "btn btn-success w-100"
    })

class MatchSearchForm(FlaskForm):
    """Form for searching matches"""
    home_team = StringField('Home Team (Optional)',
                           validators=[Optional(), Length(max=100)],
                           render_kw={
                               "placeholder": "Search home team",
                               "class": "form-control"
                           })
    
    away_team = StringField('Away Team (Optional)',
                           validators=[Optional(), Length(max=100)],
                           render_kw={
                               "placeholder": "Search away team",
                               "class": "form-control"
                           })
    
    league = SelectField('League (Optional)',
                        choices=[('', 'All Leagues')],
                        default='',
                        render_kw={
                            "class": "form-control"
                        })
    
    start_date = DateField('Start Date (Optional)',
                          format='%Y-%m-%d',
                          validators=[Optional()],
                          render_kw={
                              "class": "form-control",
                              "placeholder": "YYYY-MM-DD"
                          })
    
    end_date = DateField('End Date (Optional)',
                        format='%Y-%m-%d',
                        validators=[Optional()],
                        render_kw={
                            "class": "form-control",
                            "placeholder": "YYYY-MM-DD"
                        })
    
    match_status = SelectField('Match Status',
                              choices=[
                                  ('', 'All Statuses'),
                                  ('scheduled', 'Scheduled'),
                                  ('ongoing', 'Ongoing'),
                                  ('completed', 'Completed'),
                                  ('cancelled', 'Cancelled')
                              ],
                              default='',
                              render_kw={"class": "form-control"})
    
    submit = SubmitField('Search Matches', render_kw={
        "class": "btn btn-primary w-100"
    })

class MatchUpdateForm(FlaskForm):
    """Form for updating match details"""
    home_team = StringField('Home Team',
                           validators=[DataRequired(), Length(max=100)],
                           render_kw={
                               "class": "form-control"
                           })
    
    away_team = StringField('Away Team',
                           validators=[DataRequired(), Length(max=100)],
                           render_kw={
                               "class": "form-control"
                           })
    
    league = StringField('League',
                        validators=[DataRequired(), Length(max=100)],
                        render_kw={
                            "class": "form-control"
                        })
    
    match_date = DateField('Match Date',
                          format='%Y-%m-%d',
                          validators=[DataRequired()],
                          render_kw={"class": "form-control"})
    
    match_time = StringField('Match Time',
                            validators=[Optional(), Length(max=10)],
                            render_kw={
                                "class": "form-control",
                                "placeholder": "HH:MM"
                            })
    
    home_odds = FloatField('Home Odds',
                          validators=[Optional(), NumberRange(min=1.0)],
                          render_kw={
                              "class": "form-control",
                              "placeholder": "e.g., 2.50"
                          })
    
    draw_odds = FloatField('Draw Odds',
                          validators=[Optional(), NumberRange(min=1.0)],
                          render_kw={
                              "class": "form-control",
                              "placeholder": "e.g., 3.20"
                          })
    
    away_odds = FloatField('Away Odds',
                          validators=[Optional(), NumberRange(min=1.0)],
                          render_kw={
                              "class": "form-control",
                              "placeholder": "e.g., 2.80"
                          })
    
    submit = SubmitField('Update Match', render_kw={
        "class": "btn btn-warning"
    })

class VerificationForm(FlaskForm):
    """Form for email verification"""
    verification_code = StringField('Verification Code', 
                                  validators=[
                                      DataRequired(),
                                      Length(min=6, max=6, message='Code must be 6 digits'),
                                      Regexp(r'^\d{6}$', message='Code must contain only digits')
                                  ],
                                  render_kw={
                                      "class": "form-control text-center",
                                      "placeholder": "Enter 6-digit code",
                                      "maxlength": "6",
                                      "autocomplete": "off",
                                      "style": "font-size: 1.5rem; letter-spacing: 5px;"
                                  })
    
    submit = SubmitField('Verify Email', 
                        render_kw={"class": "btn btn-primary btn-lg w-100"})