resource "local_file" "buz" {
  content  = "buz!"
  filename = "${path.module}/buz.txt"
}
