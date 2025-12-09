with open("d:\\JRPG\\world.py", "r") as f:
    lines = f.readlines()

with open("d:\\JRPG\\world.py", "w") as f:
    f.writelines(lines[:203])

print("File cleaned!")
