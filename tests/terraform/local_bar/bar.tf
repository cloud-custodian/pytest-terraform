resource "local_file" "bar" {
   content = "bar!"
   filename = "${path.module}/bar.txt"
}
