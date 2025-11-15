import random

min=1
max=50
count=0
target=random.randint(min,max)
print("猜數字遊戲\n")
while True:
    keyin=int(input(f"猜數字範圍{min}~{max}:"))
    count+=1
    if keyin >= min and keyin <=max:
        if target == keyin:
            print(f"Bingo! 答案是:{target}")
            print(f"你猜了{count}次")
            break
        elif(keyin>target):
            print("再小一點")
            max= keyin-1
        elif(keyin<target):
            print("再大一點")
            min= keyin+1
        print(f"您已經猜了{count}次了")
    else:
        print("請輸入提示範圍內的數字")
    playagain=input("還要再玩一次嗎?")
    if playagain=='n':
        break
print("遊戲結束")