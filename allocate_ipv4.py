#!/usr/bin/env python3
"""
Allocate and associate an Elastic IP address to the current EC2 instance.
Returns the allocated IP address for use in applications.
"""

import boto3
import json
import sys
import time
from botocore.exceptions import ClientError, NoCredentialsError

def get_instance_id():
    """Get the current EC2 instance ID from metadata service."""
    try:
        import urllib.request
        response = urllib.request.urlopen(
            'http://169.254.169.254/latest/meta-data/instance-id',
            timeout=5
        )
        return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error getting instance ID: {e}", file=sys.stderr)
        return None

def allocate_and_associate_eip():
    """Allocate an Elastic IP and associate it with the current instance."""
    try:
        # Initialize EC2 client
        ec2 = boto3.client('ec2')
        
        # Get current instance ID
        instance_id = get_instance_id()
        if not instance_id:
            return {"error": "Could not determine instance ID"}
        
        print(f"Instance ID: {instance_id}")
        
        # Allocate Elastic IP
        print("Allocating Elastic IP...")
        allocation = ec2.allocate_address(Domain='vpc')
        allocation_id = allocation['AllocationId']
        public_ip = allocation['PublicIp']
        
        print(f"Allocated IP: {public_ip} (Allocation ID: {allocation_id})")
        
        # Associate with current instance
        print("Associating IP with instance...")
        association = ec2.associate_address(
            InstanceId=instance_id,
            AllocationId=allocation_id
        )
        
        association_id = association['AssociationId']
        print(f"Association successful (Association ID: {association_id})")
        
        # Wait a moment for the association to take effect
        time.sleep(3)
        
        # Return success result
        result = {
            "success": True,
            "public_ip": public_ip,
            "allocation_id": allocation_id,
            "association_id": association_id,
            "instance_id": instance_id
        }
        
        # Save allocation info for release script
        with open('/tmp/eip_allocation.json', 'w') as f:
            json.dump(result, f)
        
        print(f"IPv4 address {public_ip} successfully allocated and associated!")
        return result
        
    except NoCredentialsError:
        error_msg = "AWS credentials not found. Ensure IAM role or credentials are configured."
        print(f"Error: {error_msg}", file=sys.stderr)
        return {"error": error_msg}
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        print(f"AWS Error ({error_code}): {error_msg}", file=sys.stderr)
        return {"error": f"{error_code}: {error_msg}"}
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"Error: {error_msg}", file=sys.stderr)
        return {"error": error_msg}

if __name__ == "__main__":
    result = allocate_and_associate_eip()
    
    if "error" in result:
        sys.exit(1)
    else:
        # Print JSON result for programmatic use
        print(json.dumps(result, indent=2))
        sys.exit(0)
