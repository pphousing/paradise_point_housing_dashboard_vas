from flask import Flask, render_template, request
import pandas as pd
import os
from google.oauth2.credentials import Credentials
import gspread
from google.auth.transport.requests import Request
import googlemaps
from dotenv import load_dotenv
from datetime import datetime
from dateutil.relativedelta import relativedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Load environment variables from .env file
load_dotenv()
print("GOOGLE_MAPS_API_KEY:", os.environ.get("GOOGLE_MAPS_API_KEY"))

app = Flask(__name__)

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
gmaps = googlemaps.Client(key=os.environ.get("GOOGLE_MAPS_API_KEY"))

def authenticate_google():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def get_data():
    creds = authenticate_google()
    client = gspread.authorize(creds)
    sheet = client.open('General')
    data = sheet.worksheet("ReverseArbitrage").get_all_records()
    df = pd.DataFrame(data)
    df['Move In Date'] =pd.to_datetime(df['Move In Date'], format="%m/%d/%Y",errors='coerce')
    df['date_month'] = pd.to_datetime(df['Move In Date'].apply(lambda x: x.strftime("%Y-%m")), format="%Y-%m",errors='coerce')
    df['length_of_stay_num'] = df['Length of Stay'].apply(lambda x: x.split(' ')[0]).astype(float)
    df['total_profit'] = df['Profit From Rent Spread'] + df['Revenue From Fees']
    df['Extended'] = df['Move Out Date'] !=df['Original Move Out Date']
    df['Move Out Date'] = pd.to_datetime(df['Move Out Date'], format="%m/%d/%Y",errors='coerce')
    df['Original Move Out Date'] = pd.to_datetime(df['Original Move Out Date'], format="%m/%d/%Y",errors='coerce')
    df['Extended'] = df['Move Out Date'] >df['Original Move Out Date']
    df['num_days_extended'] = (df['Move Out Date'] - df['Original Move Out Date']).apply(lambda x: x.days)
    df['Truncated Date'] = pd.to_datetime(df['Truncated Date'], format="%Y-%m",errors='coerce')


    sheet = client.open('Reverse Arbitrage Leads')
    data = sheet.worksheet("Paradise Point Housing CRM").get_all_records()
    ra = pd.DataFrame(data)
    ra = ra[ra['Lead ID'].notna()].sort_values(by='Date of Lead')
    ra = ra[ra['Date of Lead']>='2025-03-21']
    ra['Date of Lead'] = pd.to_datetime(ra['Date of Lead'])
    ra['date_month'] = pd.to_datetime(ra['Date of Lead'].apply(lambda x: x.strftime("%Y-%m")))
    return df, ra


@app.route('/')
def dashboard():
    # Assume df and ra are already loaded DataFrames
    df,ra = get_data()
    today = datetime.today()
    next_month = pd.to_datetime((today + relativedelta(months=1)).strftime("%Y-%m"))


    expiring_soon_df = df[df['Days From Lease End Date'].between(1,14) & (df['Insurance RSD']!='')].sort_values(by='Days From Lease End Date')[['Booking ID','PPH Relocation Specialist','Move In Date','Move Out Date','Length of Stay',
    'Landlord','Landlord Phone Number', 'Landlord Email Address','Tenant Name','Tenant Phone Number','Tenant Email Address',
    'Address','Notes','Days From Lease End Date','Insurance RSD','Landlord RSD']].drop_duplicates()

    pending_rsd_df = df[(df['Days From Lease End Date'] <= 0) & 
                    (df['LL Returned Security Deposit?'] == 'No')].sort_values(by='Days From Lease End Date')[['Booking ID','PPH Relocation Specialist','Move In Date','Move Out Date','Length of Stay',
    'Landlord','Landlord Phone Number', 'Landlord Email Address','Tenant Name','Tenant Phone Number','Tenant Email Address',
    'Address','Notes','Days From Lease End Date','Insurance RSD','Landlord RSD']]

    today = datetime.today()
    dates =[pd.to_datetime(today.strftime("%Y-%m")), next_month]

 
    return render_template('index.html',
                           expiring_soon=expiring_soon_df.to_dict(orient='records') if not expiring_soon_df.empty else [],
                           pending_rsd=pending_rsd_df.to_dict(orient='records'),
                          )

if __name__ == '__main__':
    # app.run(debug=True)
    # Use the PORT environment variable or default to 5000 for local testing
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)