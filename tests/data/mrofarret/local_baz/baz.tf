resource "local_file" "baz" {
   content = "baz!"
   filename = "${path.module}/baz.txt"
}
