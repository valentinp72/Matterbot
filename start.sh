conda activate matterbot
nohup python3 spotify.py > out.log 2>&1 <&- &
