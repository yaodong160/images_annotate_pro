# ===== 前端仓库 =====
git -C e:\flask_learn\react_pro config user.email "yaodong160@126.com"
git -C e:\flask_learn\react_pro config user.name "yaodong160"
git -C e:\flask_learn\react_pro commit -m "Update env config"
git -C e:\flask_learn\react_pro push origin main

# ===== 后端仓库 =====
git -C e:\flask_learn\images_annotate_pro config user.email "yaodong160@126.com"
git -C e:\flask_learn\images_annotate_pro config user.name "yaodong160"
git -C e:\flask_learn\images_annotate_pro add .
git -C e:\flask_learn\images_annotate_pro commit -m "Init: Flask backend"
git -C e:\flask_learn\images_annotate_pro remote add origin git@github.com:yaodong160/images_annotate_pro.git
git -C e:\flask_learn\images_annotate_pro push -u origin main

git -C e:\flask_learn\react_pro commit --no-verify -m "Update env config"

git config --local -l

git -C e:\flask_learn\images_annotate_pro remote set-url origin https://github.com/yaodong160/images_annotate_pro.git
git -C e:\flask_learn\images_annotate_pro push -u origin main
