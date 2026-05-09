module "civic_access_prod" {
  source = "../../modules/platform"

  environment = "prod"
  project     = "civic-access-index"
}

