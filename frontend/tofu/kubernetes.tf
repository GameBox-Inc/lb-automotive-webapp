resource "kubernetes_deployment" "app" {
  metadata {
    name = "lb-automotive-app"
    labels = {
      app = "lb-automotive-app"
    }
  }

  spec {
    replicas = 2

    selector {
      match_labels = {
        app = "lb-automotive-app"
      }
    }

    template {
      metadata {
        labels = {
          app = "lb-automotive-app"
        }
      }

      spec {
        container {
          image = "${azurerm_container_registry.main.login_server}/${var.app_image_name}:latest"
          name  = "lb-automotive-app"

          port {
            container_port = 80
          }
        }
      }
    }
  }
}

resource "kubernetes_service" "app" {
  metadata {
    name = "lb-automotive-service"
  }
  spec {
    selector = {
      app = kubernetes_deployment.app.metadata.0.labels.app
    }
    port {
      port        = 80
      target_port = 80
    }
    type = "LoadBalancer"
  }
}

output "app_url" {
  value = kubernetes_service.app.status.0.load_balancer.0.ingress.0.ip
}
