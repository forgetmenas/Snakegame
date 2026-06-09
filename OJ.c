#include<stdio.h>
#include<stdlib.h>
#include<string.h>
#include<stdbool.h>
#define MAX 400
#define INF 0x3f3f3f3f

typedef struct Position{
    signed char x, y;
}Position;
typedef struct State{
    char map[20][21]; // 地图
    Position snake[400]; // 蛇身
    int h, t; // 头尾索引
    int dir; // 当前方向
    int score;
    int step; // 已走步数
    int N; // 每N步自动增长
    Position food;
    int foodExist;
    int len; // 蛇长
}State, *StatePtr;

int dx[4] = {-1, 0, 1, 0}, dy[4] = {0, -1, 0, 1};
char direction[4] = {'W', 'A', 'S', 'D'};
char BaseBlock[20][20], FoodPlan[405];
Position NextFood, FoodTarget; // 下一个食物, 目标食物
int NextFoodExist, FoodLen, FoodPos; // _, 规划路径长度, _
StatePtr Game;

int DirID(char dir);
void InitGame(StatePtr s);
int go(StatePtr s, int dir);
void Move(StatePtr s, char dir);
int BFS(StatePtr s, Position target, int allowTail, int allowFood, int *Dist, char route[]);
int flood(StatePtr s, Position st); // 洪水
char where(StatePtr s);
void Output(char dir, int score);
int Input(StatePtr S);
void Print(StatePtr s);

int main()
{
    Game = (StatePtr)malloc(sizeof(State));
    InitGame(Game);

    while(true){
        char dir = where(Game);
        int cur = Game->score;
        Output(dir, cur);
        if(Input(Game) == -1) break;
        Move(Game, dir);
        // 放置新食物
        if(NextFoodExist){
            Game->food = NextFood;
            Game->foodExist = 1;
            Game->map[Game->food.x][Game->food.y] = 'F';
            NextFoodExist = 0;
        }
    }
    Print(Game);
    return 0;
}
void Output(char dir, int score)
{
    printf("%c\n%d\n", dir, score);
    fflush(stdout);
}
int Input(StatePtr s)
{
    int r, c;
    if(scanf("%d%d", &r, &c) != 2) return -1;
    NextFoodExist = 0;

    if(r == 100 && c == 100) return -1;
    if(r == 20 && c == 20) return 0;
    if(r > 0 && r < 19 && c > 0 && c < 19){
        NextFood.x = r, NextFood.y = c, NextFoodExist = 1;
        return 1;
    }

    return 0;
}
void Print(StatePtr s)
{
    for(int i = 0; i < 20; i++) printf("%s\n", s->map[i]);
    printf("%d\n", s->score);
}
// 方向字符转索引
int DirID(char dir)
{
    if(dir == 'W') return 0;
    if(dir == 'A') return 1;
    if(dir == 'S') return 2;
    return 3;
}
void InitGame(StatePtr s)
{
    for(int i = 0; i < 20; i++){
        scanf("%20s", s->map[i]);
        s->map[i][20] = '\0';
    }

    scanf("%d", &s->N);
    Position head, pre, cur;
    head.x = -1; head.y = -1, pre.x = -1; pre.y = -1;
    s->foodExist = 0, s->len = 0;
    // 标记障碍物/蛇头/食物
    for(int i = 0; i < 20; i++){
        for(int j = 0; j < 20; j++){
            BaseBlock[i][j] = (s->map[i][j] == '#' || s->map[i][j] == 'O');
            if(s->map[i][j] == 'H') head.x = i, head.y = j;
            else if(s->map[i][j] == 'F') s->food.x = i, s->food.y = j, s->foodExist = 1;
        }
    }
    s->snake[s->len++] = head, cur = head;
    // 构建蛇身
    while(true){
        int found = 0;
        for(int i = 0; i < 4; i++){
            Position next;
            next.x = cur.x + dx[i], next.y = cur.y + dy[i];

            if(next.x < 0 || next.x >= 20 || next.y < 0 || next.y >= 20) continue;
            if(s->map[next.x][next.y] != 'B') continue;
            if(next.x == pre.x && next.y == pre.y) continue;

            s->snake[s->len++] = next;
            pre = cur;
            cur = next;
            found = 1;
            break;
        }
        if(found == 0) break;
    }
    s->t = s->len - 1, s->h = 0, s->dir = 0, s->score = 0, s->step = 0;
}
// 判断dir方向是否可走
int go(StatePtr s, int dir)
{
    Position next;
    if (s->dir == 0 && dir == 2) return 0; // 反方向不可走
    if (s->dir == 2 && dir == 0) return 0;
    if (s->dir == 1 && dir == 3) return 0;
    if (s->dir == 3 && dir == 1) return 0;
    next = s->snake[s->h];
    if(dir == 0) next.x--;
    else if(dir == 1) next.y--;
    else if(dir == 2) next.x++;
    else next.y++;

    if(next.x < 0 || next.x >= 20 || next.y < 0 || next.y >= 20) return 0;
    if(s->map[next.x][next.y] == '#' || s->map[next.x][next.y] == 'O') return 0;
    if(s->map[next.x][next.y] == 'B' || s->map[next.x][next.y] == 'H'){
        int grow = 0;
        if(s->foodExist && s->food.x == next.x && s->food.y == next.y) grow = 1;
        if(s->N > 0 && (s->step + 1) % s->N == 0) grow = 1;
        Position tail = s->snake[s->t];
        if(next.x == tail.x && next.y == tail.y && grow == 0) return 1; // 尾部避让
        else return 0;
    }

    return 1;
}
// 吃食物/增长/尾部收缩
void Move(StatePtr s, char dir)
{
    s->step++;
    Position head = s->snake[s->h], tail = s->snake[s->t];
    Position next = head;
    int food, flag = 0, id = DirID(dir);

    if(dir == 'W') next.x--;
    else if(dir == 'A') next.y--;
    else if(dir == 'S') next.x++;
    else if(dir == 'D') next.y++;

    food = s->foodExist && s->food.x == next.x && s->food.y == next.y;
    if(food || (s->N > 0 && s->step % s->N == 0)) flag = 1;
    s->map[head.x][head.y] = 'B'; // 旧蛇头变蛇身
    s->h = (s->h - 1 + MAX) % MAX;
    s->snake[s->h] = next;
    if(flag == 0) s->map[tail.x][tail.y] = '.', s->t = (s->t - 1 + MAX) % MAX; // 尾部收缩
    else s->len++;
    s->dir = id;
    s->map[next.x][next.y] = 'H';
    if(food) s->score += 10, s->foodExist = 0;
}
int BFS(StatePtr s, Position target, int allowTail, int allowFood, int *Dist, char route[])
{
    char block[20][20], vis[20][20], pred[20][20], temp[405];
    signed char prex[20][20], prey[20][20];
    Position q[405];
    Position st = s->snake[s->h];
    int h = 0, t = 0, len = 0;

    if(!(target.x >= 1 && target.x <= 18 && target.y >= 1 && target.y <= 18)){
        if(Dist) *Dist = INF;
        return -1;
    }

    memset(vis, 0, sizeof(vis));
    memcpy(block, BaseBlock, sizeof(BaseBlock));
    // 蛇身标记为障碍
    for(int k = 0, i = s->h; k < s->len; k++, i = (i + 1) % MAX){
        if(allowTail && i == s->t) continue;
        block[s->snake[i].x][s->snake[i].y] = 1;
    }   
    if(allowFood && s->foodExist) block[s->food.x][s->food.y] = 0;
    block[st.x][st.y] = 0, block[target.x][target.y] = 0;
    q[t++] = st;
    vis[st.x][st.y] = 1;
    prex[st.x][st.y] = st.x, prey[st.x][st.y] = st.y;

    while(h < t){
        Position cur = q[h++];
        if(cur.x == target.x && cur.y == target.y) break;
        for(int i = 0; i < 4; i++){
            Position next;
            next.x = cur.x + dx[i], next.y = cur.y + dy[i];
            if(!(next.x >= 1 && next.x <= 18 && next.y >= 1 && next.y <= 18)) continue;
            if(block[next.x][next.y] || vis[next.x][next.y]) continue;
            vis[next.x][next.y] = 1;
            prex[next.x][next.y] = cur.x, prey[next.x][next.y] = cur.y, pred[next.x][next.y] = direction[i];
            q[t++] = next;
        }
    }

    if(!vis[target.x][target.y]){
        if(Dist) *Dist = INF;
        return -1;
    }
    // 从目标回溯构建路径
    Position cur = target;
    while(cur.x != st.x || cur.y != st.y){
        temp[len++] = pred[cur.x][cur.y];
        int x = prex[cur.x][cur.y], y = prey[cur.x][cur.y];
        cur.x = x, cur.y = y;
    }

    if(Dist) *Dist = len;
    if(len == 0) return -1;
    if(route){
        for(int i = 0; i < len; i++) route[i] = temp[len - 1 - i];
        route[len] = '\0';
        return DirID(route[0]);
    }

    return DirID(temp[len - 1]);
}
// 从st出发的可达面积
int flood(StatePtr s, Position st)
{
    char block[20][20], vis[20][20];
    Position q[405];
    int h = 0, t = 0, area = 0;
    memcpy(block, BaseBlock, sizeof(BaseBlock));

    for(int k = 0, i = s->h; k < s->len; k++, i = (i + 1) % MAX){
        if(s->N != 1 && i == s->t) continue;
        block[s->snake[i].x][s->snake[i].y] = 1;
    }
    if(s->foodExist) block[s->food.x][s->food.y] = 0;
    memset(vis, 0, sizeof(vis));
    block[st.x][st.y] = 0;
    q[t++] = st;
    vis[st.x][st.y] = 1;

    while(h < t){
        Position cur = q[h++];
        area++;
        for(int i = 0; i < 4; i++){
            Position next;
            next.x = cur.x + dx[i], next.y = cur.y + dy[i];
            if(next.x < 1 || next.x > 18 || next.y < 1 || next.y > 18) continue;
            if(block[next.x][next.y] || vis[next.x][next.y]) continue;
            vis[next.x][next.y] = 1;
            q[t++] = next;
        }
    }

    return area;
}
// 选择最优方向
char where(StatePtr s)
{
    char route[405];
    int dist = 0;
    // 检查缓存的食物路径是否可复用
    if(s == Game && FoodPos < FoodLen){
        if(s->foodExist && s->food.x == FoodTarget.x && s->food.y == FoodTarget.y){
            int id = DirID(FoodPlan[FoodPos]);
            if(go(s, id)) return FoodPlan[FoodPos++];
        }
        FoodLen = FoodPos = 0;
    }
    // 尝试走向食物
    if(s->foodExist && BFS(s, s->food, 0, 1, &dist, route) >= 0){
        StatePtr temp = (StatePtr)malloc(sizeof(State));
        memcpy(temp, s, sizeof(State));
        int Safe = 1;

        for(int i = 0; i < dist; i++){
            int ID = DirID(route[i]);
            if(!go(temp, ID)){
                Safe = 0;
                break;
            }
            Move(temp, route[i]);
        }

        if(Safe){
            if(temp->len <= 1 || BFS(temp, temp->snake[temp->t], temp->N != 1, 1, NULL, NULL) >= 0){
                free(temp);
                return route[0];
            }
        }

        free(temp);
    }

    char BestDir = '\0';
    int maxSafe = -1, maxTail = -1, maxArea = -1;
    // 枚举四方向选最优
    for(int i = 3; i >= 0; i--){
        if (s->dir == 0 && i == 2) continue;
        if (s->dir == 2 && i == 0) continue;
        if (s->dir == 1 && i == 3) continue;
        if (s->dir == 3 && i == 1) continue;
        if(!go(s, i)) continue; 
        StatePtr temp = (StatePtr)malloc(sizeof(State));
        memcpy(temp, s, sizeof(State));
        Move(temp, direction[i]);
        int CurArea = flood(temp, temp->snake[temp->h]);
        int TailDis = 0;
        int Tail = (BFS(temp, temp->snake[temp->t], temp->N != 1, 1, &TailDis, NULL) >= 0);

        if (!Tail) TailDis = 0;
        int Better = 0;
        if(Tail > maxSafe) Better = 1;     
        else if(Tail == maxSafe){
            if (TailDis > maxTail) Better = 1;
            else if(TailDis == maxTail){
                if (CurArea > maxArea) Better = 1;
            }
        }

        if(Better) maxSafe = Tail, maxTail = TailDis, maxArea = CurArea, BestDir = direction[i];
        free(temp);
    }
    
    if(BestDir != '\0') return BestDir;
    return direction[s->dir];
}