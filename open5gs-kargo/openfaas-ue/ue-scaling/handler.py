import json
import time
from kubernetes import client, config
from kubernetes.client.rest import ApiException

def scale_deployment(apps_v1, name, namespace, replicas):
    """Helper function to scale a deployment"""
    try:
        patch = {"spec": {"replicas": replicas}}
        apps_v1.patch_namespaced_deployment(
            name=name,
            namespace=namespace,
            body=patch
        )
        return True
    except ApiException as e:
        return False

def wait_for_deployment(apps_v1, name, namespace, desired_replicas, timeout=120):
    """Helper function to wait for deployment to reach desired replicas"""
    start_time = time.time()
    while True:
        deployment = apps_v1.read_namespaced_deployment(
            name=name,
            namespace=namespace
        )
        if deployment.status.ready_replicas == desired_replicas:
            return True
            
        if time.time() - start_time > timeout:
            return False
            
        time.sleep(5)

def check_pod_logs(core_v1, pod_name, namespace, success_message, timeout=120):
    """Helper function to check pod logs for success message"""
    start_time = time.time()
    while True:
        try:
            logs = core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=100
            )
            if success_message in logs:
                return True, logs
                
        except ApiException:
            pass  # Pod might not be ready yet
            
        if time.time() - start_time > timeout:
            return False, "Timeout waiting for success message in logs"
            
        time.sleep(5)

def handle(req):
    """
    OpenFaaS function to manage UERANSIM deployments:
    1. Scale up UE deployment in core5g namespace
    2. Wait for PDU session setup
    3. Scale down both UE and gNB deployments
    """
    try:
        # Load Kubernetes configuration
        config.load_incluster_config()
        apps_v1 = client.AppsV1Api()
        core_v1 = client.CoreV1Api()
        
        # Configuration
        ue_config = {
            "name": "ueransim-ue",
            "namespace": "core5g",
            "success_message": "Connection setup for PDU session[1] is successful, TUN interface"
        }
        gnb_config = {
            "name": "ueransim-gnb",
            "namespace": "core5g"
        }
        
        try:
            # Check if UE deployment exists
            deployment = apps_v1.read_namespaced_deployment(
                name=ue_config["name"],
                namespace=ue_config["namespace"]
            )
            
            # Scale up UE deployment to 1
            if not scale_deployment(apps_v1, ue_config["name"], ue_config["namespace"], 1):
                return json.dumps({
                    "status": "error",
                    "message": "Failed to scale up UE deployment",
                    "logs": None
                })
            
            # Wait for UE deployment to be ready
            if not wait_for_deployment(apps_v1, ue_config["name"], ue_config["namespace"], 1):
                return json.dumps({
                    "status": "error",
                    "message": "Timeout waiting for UE deployment to be ready",
                    "logs": None
                })
            
            # Get UE pod name
            pods = core_v1.list_namespaced_pod(
                namespace=ue_config["namespace"],
                label_selector=f"app={ue_config['name']}"
            )
            
            if not pods.items:
                return json.dumps({
                    "status": "error",
                    "message": "No UE pods found",
                    "logs": None
                })
            
            ue_pod_name = pods.items[0].metadata.name
            
            # Check UE logs for PDU session success
            success, logs = check_pod_logs(
                core_v1, 
                ue_pod_name, 
                ue_config["namespace"],
                ue_config["success_message"]
            )
            
            if not success:
                return json.dumps({
                    "status": "error",
                    "message": "PDU session setup not detected",
                    "logs": logs
                })
            
            # Scale down both deployments
            scale_results = []
            
            # Scale down UE
            ue_scale_down = scale_deployment(
                apps_v1, 
                ue_config["name"], 
                ue_config["namespace"], 
                0
            )
            scale_results.append(f"UE scale down: {'successful' if ue_scale_down else 'failed'}")
            
            # Scale down gNB
            gnb_scale_down = scale_deployment(
                apps_v1, 
                gnb_config["name"], 
                gnb_config["namespace"], 
                0
            )
            scale_results.append(f"gNB scale down: {'successful' if gnb_scale_down else 'failed'}")
            
            return json.dumps({
                "status": "success" if all([ue_scale_down, gnb_scale_down]) else "warning",
                "message": "Operation completed. " + ", ".join(scale_results),
                "logs": logs
            })
                
        except ApiException as e:
            if e.status == 404:
                return json.dumps({
                    "status": "error",
                    "message": "UERANSIM UE deployment not found",
                    "logs": None
                })
            else:
                return json.dumps({
                    "status": "error",
                    "message": f"Kubernetes API error: {str(e)}",
                    "logs": None
                })
                
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Function error: {str(e)}",
            "logs": None
        })

def main():
    handle(None)

if __name__ == "__main__":
    main()