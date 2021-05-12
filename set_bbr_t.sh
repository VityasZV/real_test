cd bbr
make 
sudo rmmod tcp_bbr_t
sudo insmod tcp_bbr_t.ko
# sudo sysctl -w net.ipv4.tcp_congestion_control=cubic_t
sudo dmesg -C
cd ..
