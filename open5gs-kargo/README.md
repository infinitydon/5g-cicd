## 5G Deployment LifeCycle Using Kargo

This document  is to provide details of how the necessary infrastructure were created for using Kargo to manage the promotion of Helm charts version across dev and prod Kubernetes clusters.

For this write-up, 2 promox VMs with additional NIC for the multus network were used.

Alternative virtualization software can be used but the concept should be the same.

VM1 - This will be  used as the  dev cluster and it will also be where ArgoCD and Kargo will only be installed.

VM2 - This will be used only as the prod cluster and it must be registered as a remote cluster in ArgoCD.

k0s was used to create the k8s clusters (single node cluster).

## Install k8s cluster on  both VMs
echo -e "network:\n  version: 2\n  renderer: networkd\n  ethernets:\n    ens19:\n      dhcp4: no\n      dhcp6: no\n      optional: true\n      addresses: []" | sudo tee /etc/netplan/99-ens19.yaml > /dev/null && sudo netplan apply

N.B - ens19 is the additional NIC that is required for multus, this may be a different name depending on your OS or VM platform.

curl -sSLf https://get.k0s.sh | sudo sh
sudo k0s install controller --single
sudo k0s start

curl -LO https://dl.k8s.io/release/v1.32.0/bin/linux/amd64/kubectl
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

echo 'source <(kubectl completion bash)' >>~/.bashrc

source ~/.bashrc

curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

mkdir ~/.kube
sudo k0s kubeconfig admin > .kube/config

## Dev Cluster i.e. VM1

## Install required software on Dev cluster

sudo apt install apache2-utils -y

helm repo add jetstack https://charts.jetstack.io --force-update

helm install \
  cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.16.1 \
  --set crds.enabled=true

kubectl apply -f https://github.com/infinitydon/nephio-proxmox-packages/raw/refs/heads/r3/multus-package/multus-thickplugin.yaml

kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.8/config/manifests/metallb-native.yaml

```
cat <<EOF | kubectl apply -f-
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: faas-pool
  namespace: metallb-system
spec:
  addresses:
  - 10.0.10.1-10.0.10.10
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: fasas
  namespace: metallb-system
spec:  
  interfaces:
  - eth0  
EOF
```

kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.1/cert-manager.yaml

kubectl create ns argocd

kubectl -n argocd apply -f https://github.com/argoproj/argo-cd/raw/refs/tags/v2.13.0/manifests/install.yaml

kubectl patch svc argocd-server -n argocd -p '{"spec": {"type": "LoadBalancer"}}'

kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d; echo

curl -sSL -o argocd-linux-amd64 https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64

sudo install -m 555 argocd-linux-amd64 /usr/local/bin/argocd

rm argocd-linux-amd64


kubectl create namespace argo-rollouts

kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/download/v1.7.2/install.yaml

pass="nLIlShGRcSIMTnSsezH7"

echo "Password: $pass"

hashed_pass=$(htpasswd -bnBC 10 "" $pass | tr -d ':\n')

signing_key="jzKIHqB0XwjSTfgpTdPjtptUtfVnU5Lx"

helm upgrade --install kargo \
  oci://ghcr.io/akuity/kargo-charts/kargo \
  --namespace kargo \
  --create-namespace \
  --set api.adminAccount.passwordHash=$hashed_pass \
  --set api.adminAccount.tokenSigningKey=$signing_key \
  --set api.service.type=LoadBalancer \
  --wait

## OpenFaaS
curl -SLsf https://get.arkade.dev/ | sudo sh

arkade install openfaas --load-balancer

arkade get faas-cli

sudo mv /home/ubuntu/.arkade/bin/faas-cli /usr/local/bin/

kubectl create ns core5g

kubectl apply -f openfaas-ue/kubernetes-rbac.yaml 

kubectl apply -f openfaas-gnb/kubernetes-rbac.yaml

export OPENFAAS_URL=http://10.0.10.1:8080/ (this will be the LB IP, modify if necessary)

PASSWORD=$(kubectl get secret -n openfaas basic-auth -o jsonpath="{.data.basic-auth-password}" | base64 --decode; echo)

echo -n $PASSWORD | faas-cli login --username admin --password-stdin

## Install openfaas
Update the GW value to the LB IP that was assigned by metalLB in `gateway: http://10.0.1.1:8080/` in both gnb-scaling.yml and ue-scaling.yml

cd ~/openfaas-gnb;faas-cli deploy -f gnb-scaling.yml

cd ~/openfaas-ue;faas-cli deploy -f ue-scaling.yml

N.B - Same manifests will be used for the openfaas in the prod cluster i.e. VM2 but only the gateway IP needs to be changed.

N.B - MetalLB is optional, NodePort service can also be used or public cloud LB as applicable to your platform

## Second Cluster
kubectl apply -f https://github.com/infinitydon/nephio-proxmox-packages/raw/refs/heads/r3/multus-package/multus-thickplugin.yaml

kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.8/config/manifests/metallb-native.yaml

```
cat <<EOF | kubectl apply -f-
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: faas-pool
  namespace: metallb-system
spec:
  addresses:
  - 10.0.10.11-10.0.10.20
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: faas
  namespace: metallb-system
spec:
  interfaces:
  - eth0  
EOF
```

## Install openfaas
curl -SLsf https://get.arkade.dev/ | sudo sh

arkade install openfaas --load-balancer

arkade get faas-cli

sudo mv /home/ubuntu/.arkade/bin/faas-cli /usr/local/bin/

kubectl create ns core5g

kubectl apply -f openfaas-ue/kubernetes-rbac.yaml

kubectl apply -f openfaas-gnb/kubernetes-rbac.yaml

export OPENFAAS_URL=http://10.0.10.11:8080/ (this will be the LB IP, modify if necessary)

PASSWORD=$(kubectl get secret -n openfaas basic-auth -o jsonpath="{.data.basic-auth-password}" | base64 --decode; echo)

echo -n $PASSWORD | faas-cli login --username admin --password-stdin

## Update the gateway to the openfaas gateway for the second cluster before applying

cd ~/openfaas-gnb;faas-cli deploy -f gnb-scaling.yml

cd ~/openfaas-ue;faas-cli deploy -f ue-scaling.yml

## Register second cluster on first cluster, command must be run in first cluster
argocd login --insecure 10.0.10.2 --username admin --password BD6WfMM2AUQdRkch --skip-test-tls --grpc-web

N.B - 10.0.10.2 is the ArgoCD LB IP

N.B - You will need to copy the kubeconfig of prod cluster to the dev cluster VM

argocd cluster add --kubeconfig kargo-cicd-2-kubeconfig --kube-context string Default --name kargo-cicd-2


## Deploy the Kargo/ArgoCD manifests in the Dev cluster
```
kubectl apply -f kargo-manifest.yaml

kubectl apply -f argoccd-applicationset.yaml
```

You can now push open5gs charts to the Git repo to trigger the trivy scanning and OCI chart build.

The chart will only be pushed to the github OCI repo if all the  github-action steps result in success.