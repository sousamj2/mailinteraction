import json
import boto3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def get_parameter(parameter_name, decrypt=True):
    """Get parameter from AWS Systems Manager Parameter Store"""
    ssm = boto3.client('ssm', region_name='eu-south-2')
    try:
        # print(f"Attempting to get parameter: {parameter_name}")
        response = ssm.get_parameter(Name=parameter_name, WithDecryption=decrypt)
        # print(f"Successfully retrieved parameter: {parameter_name}")
        return response['Parameter']['Value']
    except Exception as e:
        # print(f"Error getting parameter {parameter_name}: {e}")
        return None

def send_email_via_smtp(sender, recipient, subject, html_message, smtp_server, smtp_port, smtp_password):
    """Send email using SMTP"""
    try:
        # print(f"Attempting to send email from {sender} to {recipient} via {smtp_server}:{smtp_port}")
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(html_message, 'html'))

        # Use SSL for port 465, STARTTLS for others
        if smtp_port == 465:
            # print("Using SMTP_SSL for port 465")
            with smtplib.SMTP_SSL(smtp_server, smtp_port) as smtp:
                smtp.login(sender, smtp_password)
                smtp.send_message(msg)
        else:
            # print(f"Using SMTP with STARTTLS for port {smtp_port}")
            with smtplib.SMTP(smtp_server, smtp_port) as smtp:
                smtp.starttls()
                smtp.login(sender, smtp_password)
                smtp.send_message(msg)
        
        # print("Email sent successfully")
        return True, "Email sent successfully"
    
    except Exception as e:
        # print(f"Error sending email: {str(e)}")
        return False, f"Error sending email: {str(e)}"

def lambda_handler(event, context):
    # print(f"Lambda function started. Event: {json.dumps(event)}")
    
    try:
        # Parse the incoming request
        if 'body' in event:
            # print("Parsing body from API Gateway event")
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            print("Using event directly")
            body = event
        
        print(f"Parsed body: {json.dumps(body)}")
        
        # Extract email parameters from EC2
        sender = body.get('sender')
        recipient = body.get('recipient')
        subject = body.get('subject')
        html_message = body.get('html_message')
              
        # Validate required parameters
        if not all([sender, recipient, subject, html_message]):
            error_msg = 'Missing required parameters: sender, recipient, subject, html_message, smtp_server'
            # print(f"Validation failed: {error_msg}")
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': error_msg
                })
            }
        smtp_port = 465
        
        # Determine which password parameter to use based on sender
        if 'mjcrafts' in sender.lower():
            smtp_server = 'srv9.mychrome.pt'
            password_parameter = '/dev/MC_MAIL_PASSWORD'
        else:
            smtp_server = 'webdomain02.dnscpanel.com'
            password_parameter = '/dev/EXPL_MAIL_PASSWORD'
        
        # print(f"Using password parameter: {password_parameter}")
        
        # Get password from Parameter Store
        smtp_password = get_parameter(password_parameter, decrypt=True)
        
        if not smtp_password:
            error_msg = f'Could not retrieve password from parameter: {password_parameter}'
            # print(error_msg)
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': error_msg
                })
            }
        
        # print("Password retrieved successfully")
        
        # Send the email
        success, message = send_email_via_smtp(
            sender, recipient, subject, html_message,
            smtp_server, smtp_port, smtp_password
        )
        
        result = {
            'statusCode': 200 if success else 500,
            'body': json.dumps({
                'message': message,
                'email_sent': success,
                'recipient': recipient,
                'sender': sender,
                'smtp_server': smtp_server,
                'password_parameter_used': password_parameter
            })
        }
        
        # print(f"Function completed. Result: {json.dumps(result)}")
        return result
    
    except Exception as e:
        error_msg = f'Lambda function error: {str(e)}'
        # print(error_msg)
        result = {
            'statusCode': 500,
            'body': json.dumps({
                'error': error_msg,
                'email_sent': False
            })
        }
        # print(f"Function failed. Result: {json.dumps(result)}")
        return result
