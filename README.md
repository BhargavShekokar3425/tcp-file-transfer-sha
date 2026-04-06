# TCP File Transfer with SHA-256 Visualizer

An educational simulator that combines a real TCP file transfer with a Tkinter dashboard so students can see how chunked streaming, reconstruction, integrity verification, throughput, and failure scenarios behave.

## Architecture

```text
main.py
  -> visualizer/gui.py
      -> demo/simulator.py
          -> server/file_server.py
          -> client/file_client.py
      -> visualizer/topology.py
      -> visualizer/chunk_animator.py
      -> visualizer/metrics.py
  -> protocols/protocol.py
  -> utils/hash_utils.py
```

- `server/file_server.py`: threaded TCP server that sends metadata, streams chunks, and emits visualization events.
- `client/file_client.py`: threaded TCP client that receives frames, reconstructs the file, computes SHA-256, and reports metrics.
- `demo/simulator.py`: orchestrates server/client lifecycle, pause/resume, and event delivery.
- `visualizer/`: dashboard components for topology, chunk animation, reconstruction, hash status, logs, and throughput graph.
- `protocols/protocol.py`: simple framing helpers for metadata, chunk frames, and EOF.

## Protocol

The simulator uses a small application-layer protocol on top of TCP:

1. Metadata line
   `{"filename":"sample.bin","filesize":1048576,"sha256":"...","chunk_size":1024,"total_chunks":1024,"mode":"correct"}\n`
2. Chunk streaming
   `[4-byte frame_size][4-byte sequence_number][chunk_data]`
3. End signal
   `EOF`

This stays close to the requested `FILENAME|FILESIZE|HASH\n`, `[chunk_size][data]`, `EOF` flow while also carrying a sequence number inside the chunk payload so the GUI can visualize ordering and failure modes clearly.

## Why TCP Reliability Still Needs Good Application Design

TCP ensures:

- ordered byte delivery
- retransmission of lost packets
- error detection on the transport stream
- flow control and congestion control

TCP does not automatically solve:

- application memory spikes from reading giant payloads at once
- end-to-end file integrity validation after reconstruction
- logical bugs such as assembling chunks in the wrong order
- educational visibility into what the application is doing

## Why Chunking Is Needed

- avoids reading and sending the entire file in a single memory burst
- enables progressive UI updates and throughput sampling
- supports pause/resume style demos
- makes reconstruction and debugging easier to explain

The `no_chunking` mode intentionally sends the full file as one large application chunk so students can compare behavior.

## Why SHA-256 Is Critical

- confirms the reconstructed file matches the sender’s original bytes
- catches missing, reordered, or corrupted application data
- demonstrates that successful TCP connection setup alone is not enough for integrity assurance

The `no_hash_verification` mode intentionally skips verification to show why corruption can go undetected.

## Failure Modes Included

- `correct`: chunked transfer, ordered reconstruction, SHA-256 verification
- `no_chunking`: one giant application chunk
- `no_hash_verification`: transfer completes but integrity is not checked
- `packet_loss`: the server intentionally omits chunk 5 before EOF
- `out_of_order`: the server intentionally sends chunk 3 before chunk 2, and the client in this mode reconstructs by arrival order to demonstrate failure

## Performance Insights

- throughput is sampled during receive events and shown in a live graph
- chunk size can be adjusted to explore latency vs. throughput tradeoffs
- speed limiting helps slow the transfer down so the animation remains educational
- the GUI remains responsive by using threads, `queue.Queue`, and `root.after()`

## Run

```bash
python3 main.py
```

### Terminal-only usage (no GUI)

1. Start the server (adjust `--file` and `--port` if needed):
   ```bash
   python3 -m server.file_server --file /path/to/file --port 5001 --host 127.0.0.1
   ```
2. In another terminal, start the client:
   ```bash
   python3 -m client.file_client --host 127.0.0.1 --port 5001 --out /tmp/tcp_client_out
   ```
3. To run the headless simulator (spins server + client with failure modes, logs to stdout):
   ```bash
   python3 -m demo.simulator --mode correct --chunk-size 1024 --port 5001
   ```
Notes:
- Exports to avoid import errors when running scripts directly:  
  ```bash
  export PYTHONPATH=$(pwd)
  ```
- If you run files directly (`python3 server/file_server.py`), each script now also prepends the repo root to `sys.path`. Module mode (`python3 -m ...`) is still cleaner.
- Default host/port are `127.0.0.1:5001`; edit them in the scripts or add CLI args if you extend them.

## Run components individually

- TCP server only (sends file on port 5001 by default):  
  ```bash
  python3 -m server.file_server
  ```
- TCP client only (receives from localhost:5001 and writes to /tmp by default):  
  ```bash
  python3 -m client.file_client
  ```
- Demo simulator (orchestrates server + client with event queue, useful for headless testing):  
  ```bash
  python3 -m demo.simulator
  ```
- Tkinter visualizer/dashboard standalone:  
  ```bash
  python3 -m visualizer.gui
  ```

## Run On Multiple PCs

1. Place the same project on both machines.
2. Update the host in `visualizer/gui.py` or wire a user input field for the server IP.
3. Start the server-side instance on the machine that owns the source file.
4. Start the client-side instance on the second machine and point it at the server IP.
5. Ensure the chosen TCP port is open in the OS firewall.

For classroom demos, localhost mode is simpler and already configured.

## Notes

- The GUI uses Tkinter and a custom canvas graph, so no extra plotting dependency is required.
- The included demo file is generated automatically in the system temporary directory.
