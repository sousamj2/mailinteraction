#!/usr/bin/env python3
"""
Disassociate and release the Elastic IP address from the current EC2 instance.
Uses allocation info saved by allocate_ipv4.py or accepts parameters.
"""

import boto3
import json
import sys
import os
import argparse
from botocore.exceptions import ClientError, NoCredentialsError

def load_allocation_info():
    """Load allocation info from the temporary file."""
    try:
        with open('/tmp/eip_allocation.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        print("Error: Invalid allocation info file", file=sys.stderr)
        return None

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

def release_eip(allocation_id=None, association_id=None):
    """Disassociate and release the Elastic IP."""
    try:
        # Initialize EC2 client
        ec2 = boto3.client('ec2')
        
        # Try to load allocation info if not provided
        if not allocation_id:
            allocation_info = load_allocation_info()
            if allocation_info:
                allocation_id = allocation_info.get('allocation_id')
                association_id = allocation_info.get('association_id')
                public_ip = allocation_info.get('public_ip')
                print(f"Loaded allocation info: IP {public_ip}")
            else:
                return {"error": "No allocation ID provided and no saved allocation info found"}
        
        # Disassociate the address if association_id is available
        if association_id:
            print(f"Disassociating address (Association ID: {association_id})...")
            try:
                ec2.disassociate_address(AssociationId=association_id)
                print("Address disassociated successfully")
            except ClientError as e:
                if e.response['Error']['Code'] == 'InvalidAssociationID.NotFound':
                    print("Address was already disassociated")
                else:
                    raise
        else:
            # Fallback: disassociate by allocation ID
            print(f"Disassociating address by allocation ID...")
            try:
                ec2.disassociate_address(AllocationId=allocation_id)
                print("Address disassociated successfully")
            except ClientError as e:
                if e.response['Error']['Code'] in ['InvalidAllocationID.NotFound', 'InvalidAssociation.NotFound']:
                    print("Address was already disassociated or not associated")
                else:
                    raise
        
        # Release the Elastic IP
        print(f"Releasing Elastic IP (Allocation ID: {allocation_id})...")
        ec2.release_address(AllocationId=allocation_id)
        print("Elastic IP released successfully")
        
        # Clean up the temporary file
        try:
            os.remove('/tmp/eip_allocation.json')
            print("Cleaned up allocation info file")
        except FileNotFoundError:
            pass
        
        result = {
            "success": True,
            "message": "Elastic IP successfully disassociated and released",
            "allocation_id": allocation_id
        }
        
        return result
        
    except NoCredentialsError:
        error_msg = "AWS credentials not found. Ensure IAM role or credentials are configured."
        print(f"Error: {error_msg}", file=sys.stderr)
        return {"error": error_msg}
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        
        if error_code == 'InvalidAllocationID.NotFound':
            print("Warning: Allocation ID not found (may have been already released)")
            return {"success": True, "message": "IP was already released"}
        
        print(f"AWS Error ({error_code}): {error_msg}", file=sys.stderr)
        return {"error": f"{error_code}: {error_msg}"}
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"Error: {error_msg}", file=sys.stderr)
        return {"error": error_msg}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Release Elastic IP address')
    parser.add_argument('--allocation-id', help='Allocation ID of the Elastic IP to release')
    parser.add_argument('--association-id', help='Association ID (optional, for faster disassociation)')
    
    args = parser.parse_args()
    
    result = release_eip(
        allocation_id=args.allocation_id,
        association_id=args.association_id
    )
    
    if "error" in result:
        sys.exit(1)
    else:
        print(json.dumps(result, indent=2))
        sys.exit(0)
