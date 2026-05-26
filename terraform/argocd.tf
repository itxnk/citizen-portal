# ─── ArgoCD — deployed via Helm on EKS ───────────────────────────────────────
# ArgoCD is the GitOps engine. It watches the Git repo and syncs the Helm chart
# for our app into the desc-app namespace automatically on every push to main.

resource "kubernetes_namespace" "argocd" {
  metadata {
    name = "argocd"
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
    }
  }

  depends_on = [module.eks]
}

resource "helm_release" "argocd" {
  name       = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = "6.7.18"
  namespace  = kubernetes_namespace.argocd.metadata[0].name

  values = [file("${path.module}/../argocd/install/argocd-values.yaml")]

  # Wait for all ArgoCD pods to be ready before Terraform considers this done.
  wait    = true
  timeout = 600

  set {
    name  = "global.domain"
    value = var.argocd_hostname
  }

  depends_on = [module.eks]
}

# ─── ArgoCD Application — desc-webapp ────────────────────────────────────────
# Terraform creates the ArgoCD Application CRD that points ArgoCD at our
# Helm chart in Git. After this, all future deploys are GitOps — no Terraform
# needed for application changes.

resource "kubernetes_manifest" "argocd_app_desc_webapp" {
  manifest = {
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata = {
      name      = "desc-webapp"
      namespace = "argocd"
      finalizers = ["resources-finalizer.argocd.argoproj.io"]
    }
    spec = {
      project = "desc"
      source = {
        repoURL        = var.git_repo_url
        targetRevision = "main"
        path           = "helm/desc-webapp"
        helm = {
          valueFiles = ["values.yaml"]
        }
      }
      destination = {
        server    = "https://kubernetes.default.svc"
        namespace = "desc-app"
      }
      syncPolicy = {
        automated = {
          prune    = true
          selfHeal = true
        }
        syncOptions = [
          "CreateNamespace=true",
          "PrunePropagationPolicy=foreground",
          "ServerSideApply=true"
        ]
        retry = {
          limit = 5
          backoff = {
            duration    = "5s"
            factor      = 2
            maxDuration = "3m"
          }
        }
      }
    }
  }

  depends_on = [helm_release.argocd, kubernetes_manifest.argocd_project_desc]
}

# ─── ArgoCD Application — kube-prometheus-stack ───────────────────────────────
resource "kubernetes_manifest" "argocd_app_monitoring" {
  manifest = {
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata = {
      name      = "kube-prometheus-stack"
      namespace = "argocd"
      finalizers = ["resources-finalizer.argocd.argoproj.io"]
    }
    spec = {
      project = "desc"
      source = {
        repoURL        = "https://prometheus-community.github.io/helm-charts"
        targetRevision = "58.7.2"
        chart          = "kube-prometheus-stack"
        helm = {
          valueFiles = []
          values     = file("${path.module}/../monitoring/prometheus/kube-prometheus-stack-values.yaml")
        }
      }
      destination = {
        server    = "https://kubernetes.default.svc"
        namespace = "monitoring"
      }
      syncPolicy = {
        automated = {
          prune    = true
          selfHeal = true
        }
        syncOptions = [
          "CreateNamespace=true",
          "ServerSideApply=true"
        ]
      }
    }
  }

  depends_on = [helm_release.argocd, kubernetes_manifest.argocd_project_desc]
}

# ─── ArgoCD AppProject — desc ─────────────────────────────────────────────────
resource "kubernetes_manifest" "argocd_project_desc" {
  manifest = {
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "AppProject"
    metadata = {
      name      = "desc"
      namespace = "argocd"
    }
    spec = {
      description = "DESC Cloud-Native Project"
      sourceRepos = ["*"]
      destinations = [
        { server = "https://kubernetes.default.svc", namespace = "desc-app" },
        { server = "https://kubernetes.default.svc", namespace = "monitoring" },
        { server = "https://kubernetes.default.svc", namespace = "argocd" }
      ]
      clusterResourceWhitelist = [
        { group = "*", kind = "Namespace" },
        { group = "rbac.authorization.k8s.io", kind = "ClusterRole" },
        { group = "rbac.authorization.k8s.io", kind = "ClusterRoleBinding" }
      ]
      namespaceResourceWhitelist = [
        { group = "*", kind = "*" }
      ]
    }
  }

  depends_on = [helm_release.argocd]
}
