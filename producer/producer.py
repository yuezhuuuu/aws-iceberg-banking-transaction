
"""Bank Transaction Producer - Local, Free to Run"""

import os
import time
import json
from datetime import datetime
from typing import Optional

from config import Config
from transaction_generator import TransactionGenerator


class TransactionProducer:
    """transaction producer - writes directly to local files"""
    
    def __init__(self, config: Config):
        self.config = config
        self.generator = TransactionGenerator()
        
        # statistics
        self.total_sent = 0
        self.start_time = None
    
        # output file handle and path
        self.current_file = None
        self.current_file_path = None
        self.current_file_size = 0
        self.last_rotate_time = None
        
        # Ensure output directory exists
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        
        # Open the first file
        self._open_new_file()
    
    def _get_partition_path(self) -> str:
        """get partition path (year/month/day/hour)"""
        now = datetime.now()
        return os.path.join(
            self.config.OUTPUT_DIR,
            f"year={now.year}",
            f"month={now.month:02d}",
            f"day={now.day:02d}",
            f"hour={now.hour:02d}"
        )
    
    def _get_file_name(self) -> str:
        """get file name"""
        now = datetime.now()
        return f"transactions_{now.strftime('%Y%m%d_%H%M%S')}.jsonl"
    
    def _open_new_file(self):
        """open new file"""
        # close old file
        if self.current_file:
            self.current_file.close()
            print(f"   Closed: {self.current_file_path}")
        
        # create new file
        partition_path = self._get_partition_path()
        os.makedirs(partition_path, exist_ok=True)
        
        file_name = self._get_file_name()
        self.current_file_path = os.path.join(partition_path, file_name)
        self.current_file = open(self.current_file_path, 'a', encoding='utf-8')
        self.current_file_size = 0
        self.last_rotate_time = time.time()
        
        print(f"📁 New file: {self.current_file_path}")
    
    def _should_rotate(self) -> bool:
        """check if we should rotate the file"""
        # check time threshold
        if time.time() - self.last_rotate_time >= self.config.ROTATE_SECONDS:
            return True
        
        # check size threshold
        if self.current_file_size >= self.config.ROTATE_SIZE_MB * 1024 * 1024:
            return True
        
        # check if hourly partition has changed
        current_partition = self._get_partition_path()
        if current_partition != os.path.dirname(self.current_file_path):
            return True
        
        return False
    
    def _write_transaction(self, transaction) -> bool:
        """write a single transaction"""
        try:
            # check if we should rotate
            if self._should_rotate():
                self._open_new_file()
            
            # write JSON line
            line = transaction.to_json() + '\n'
            self.current_file.write(line)
            self.current_file.flush()  # flush immediately to ensure data is not lost
            
            # update statistics
            self.current_file_size += len(line.encode('utf-8'))
            self.total_sent += 1
            
            return True
            
        except Exception as e:
            print(f"❌ Write error: {e}")
            return False
    
    def run(self, duration_seconds: Optional[int] = None):
        """run the producer
        
        Args:
            duration_seconds: the duration to run (in seconds), None means run indefinitely
        """
        self.start_time = time.time()
        target_tps = self.config.TARGET_TPS
        interval = 1.0 / target_tps
        
        print("=" * 60)
        print("🏦 Bank Transaction Log Producer")
        print("=" * 60)
        print(f"   Target TPS: {target_tps} rec/s")
        print(f"   Output dir: {self.config.OUTPUT_DIR}")
        print(f"   Rotate by: {self.config.ROTATE_SECONDS}s or {self.config.ROTATE_SIZE_MB}MB")
        print("=" * 60)
        print()
        
        last_report_time = time.time()
        last_report_count = 0
        
        try:
            while True:
                # check the runtime
                if duration_seconds and (time.time() - self.start_time) > duration_seconds:
                    break
                
                # generate and write transaction
                transaction = self.generator.generate_transaction()
                self._write_transaction(transaction)
                
                # precisely control the sending rate
                elapsed = time.time() - self.start_time
                expected = self.total_sent / target_tps
                if elapsed < expected:
                    time.sleep(expected - elapsed)
                
                # print rate report every second
                now = time.time()
                if now - last_report_time >= 1.0:
                    actual_rate = (self.total_sent - last_report_count) / (now - last_report_time)
                    print(f"📊 Rate: {actual_rate:.1f} rec/s | Total: {self.total_sent} | "
                          f"File: {os.path.basename(self.current_file_path)} | "
                          f"Size: {self.current_file_size/1024/1024:.1f}MB")
                    last_report_time = now
                    last_report_count = self.total_sent
                    
        except KeyboardInterrupt:
            print("\n⏹️  Stopping producer...")
        finally:
            # close the file
            if self.current_file:
                self.current_file.close()
            
            # final statistics
            elapsed = time.time() - self.start_time
            avg_rate = self.total_sent / elapsed if elapsed > 0 else 0
            
            print("\n" + "=" * 60)
            print("📈 Final Statistics")
            print("=" * 60)
            print(f"   Total records: {self.total_sent}")
            print(f"   Runtime: {elapsed:.1f} seconds")
            print(f"   Average rate: {avg_rate:.1f} rec/s")
            print(f"   Output directory: {self.config.OUTPUT_DIR}")
            print("=" * 60)
            
            # list generated files
            self._list_output_files()
    
    def _list_output_files(self):
        """list generated files"""
        print("\n📁 Generated files:")
        for root, dirs, files in os.walk(self.config.OUTPUT_DIR):
            level = root.replace(self.config.OUTPUT_DIR, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f'{indent}{os.path.basename(root)}/')
            subindent = ' ' * 2 * (level + 1)
            for file in sorted(files)[:10]:  # only show the first 10
                filepath = os.path.join(root, file)
                size = os.path.getsize(filepath)
                print(f'{subindent}{file} ({size/1024:.1f}KB)')
            if len(files) > 10:
                print(f'{subindent}... and {len(files)-10} more')


def main():
    """main function"""
    config = Config()
    
    try:
        config.validate()
    except AssertionError as e:
        print(f"❌ Configuration error: {e}")
        return
    
    producer = TransactionProducer(config)
    
    # run for 30 seconds, remove duration_seconds parameter to run indefinitely
    #producer.run(duration_seconds=300)  # test mode
    #producer.run()  # run indefinitely, press Ctrl+C to stop

    producer.run(duration_seconds=Config.DURATION_SECONDS if Config.DURATION_SECONDS > 0 else None)


if __name__ == "__main__":
    main()