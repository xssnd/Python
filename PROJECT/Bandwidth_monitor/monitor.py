import psutil
import time
import tkinter as tk

class BandwidthMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Bandwidth Monitor")
        self.label_upload = tk.Label(root, text="Upload Speed: ", font=('calibri', 20, 'bold'))
        self.label_upload.pack()
        
        self.label_download = tk.Label(root, text="Download Speed: ", font=('calibri', 20, 'bold'))
        self.label_download.pack()
        
        self.update_speed()

    def get_bandwidth(self):
        # Get network information
        net_io = psutil.net_io_counters()
        # get total sent and receive bandwidth in network 
        total_bytes_sent = net_io.bytes_sent
        total_bytes_recv = net_io.bytes_recv
        return total_bytes_sent, total_bytes_recv

    def calculate_speed(self, prev_bytes_sent, prev_bytes_recv, interval):
        # Get network bandwidth information
        bytes_sent, bytes_recv = self.get_bandwidth()
        # Count sent and receive speed 
        sent_speed = (bytes_sent - prev_bytes_sent) / interval
        recv_speed = (bytes_recv - prev_bytes_recv) / interval
        return sent_speed, recv_speed

    def update_speed(self):
        interval = 1  # Interval in second
        prev_bytes_sent, prev_bytes_recv = self.get_bandwidth()
        while True:
            time.sleep(interval)
            sent_speed, recv_speed = self.calculate_speed(prev_bytes_sent, prev_bytes_recv, interval)
            self.label_upload.config(text=f"Upload Speed: {sent_speed} bytes/s")
            self.label_download.config(text=f"Download Speed: {recv_speed} bytes/s")
            self.root.update()
            prev_bytes_sent, prev_bytes_recv = self.get_bandwidth()

def main():
    root = tk.Tk()
    app = BandwidthMonitorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()