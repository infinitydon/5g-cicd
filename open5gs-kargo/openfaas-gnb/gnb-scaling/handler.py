import json
import time
from kubernetes import client, config
from kubernetes.client.rest import ApiException

def handle(req):
    """
    OpenFaaS function to manage UERANSIM gNB deployment
    - Checks if deployment exists
    - Scales to 1 replica if it exists
    - Verifies AMF connection through logs
    """
    try:
        # Load Kubernetes configuration
        config.load_incluster_config()
        apps_v1 = client.AppsV1Api()
        core_v1 = client.CoreV1Api()
        
        namespace = "core5g"  # Adjust namespace as needed
        deployment_name = "ueransim-gnb"
        
        try:
            # Check if deployment exists
            deployment = apps_v1.read_namespaced_deployment(
                name=deployment_name,
                namespace=namespace
            )
            
            # Scale deployment to 1 replica if it exists
            patch = {
                "spec": {
                    "replicas": 1
                }
            }
            
            apps_v1.patch_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
                body=patch
            )
            
            # Wait for deployment to be ready
            timeout = 10  # 10 secs timeout
            start_time = time.time()
            
            while True:
                deployment = apps_v1.read_namespaced_deployment(
                    name=deployment_name,
                    namespace=namespace
                )
                
                if deployment.status.ready_replicas == 1:
                    break
                    
                if time.time() - start_time > timeout:
                    return json.dumps({
                        "status": "error",
                        "message": "Timeout waiting for deployment to be ready",
                        "logs": None
                    })
                    
                time.sleep(5)
            
            # Get pod name
            pods = core_v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=f"app={deployment_name}"
            )
            
            if not pods.items:
                return json.dumps({
                    "status": "error",
                    "message": "No pods found for deployment",
                    "logs": None
                })
            
            pod_name = pods.items[0].metadata.name
            
            # Wait for pod to be ready
            time.sleep(10)  # Give the pod some time to initialize
            
            # Get pod logs
            logs = core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=100
            )
            
            # Check for successful AMF connection
            amf_success_indicators = [
                "NG Setup procedure is successful",
                "Connected to AMF",
                "SCTP connection established"
            ]
            
            if any(indicator in logs for indicator in amf_success_indicators):
                return json.dumps({
                    "status": "success",
                    "message": "gNB deployment scaled and connected to AMF",
                    "logs": logs
                })
            else:
                return json.dumps({
                    "status": "warning",
                    "message": "gNB deployment scaled but AMF connection not detected",
                    "logs": logs
                })
                
        except ApiException as e:
            if e.status == 404:
                return json.dumps({
                    "status": "error",
                    "message": "UERANSIM gNB deployment not found",
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