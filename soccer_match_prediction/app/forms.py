from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from app.models import User

class RegistrationForm(FlaskForm):
    username = StringField('Username', 
                           validators=[DataRequired(), Length(min=2, max=20)])
    
    email = StringField('Email', 
                        validators=[DataRequired(), Email()])
    
    password = PasswordField('Password', validators=[DataRequired()])
    
    confirm_password = PasswordField('Confirm Password', 
                                     validators=[DataRequired(), EqualTo('password')])
    
    submit = SubmitField('Sign Up')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is taken. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is already in use. Please log in.')

class LoginForm(FlaskForm):
    email = StringField('Email', 
                        validators=[DataRequired(), Email()])
    
    password = PasswordField('Password', validators=[DataRequired()])
    
    remember = BooleanField('Remember Me')
    
    submit = SubmitField('Login')

class PredictForm(FlaskForm):
    # These choices are populated dynamically in routes.py based on the CSV data
    # We initialize them as empty lists here
    home_team = SelectField('Home Team', validators=[DataRequired()], choices=[])
    away_team = SelectField('Away Team', validators=[DataRequired()], choices=[])
    
    user_prediction = SelectField('Your Prediction (Optional)', 
                                  choices=[
                                      ('None', 'Skip Saving'), 
                                      ('H', 'Home Win'), 
                                      ('D', 'Draw'), 
                                      ('A', 'Away Win')
                                  ])
    
    submit = SubmitField('Analyze Match')