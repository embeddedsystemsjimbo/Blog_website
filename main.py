from flask import Flask, render_template, redirect, url_for, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterUserForm, LoginUserForm, CommentForm
from flask_gravatar import Gravatar
from sqlalchemy import exc
from functools import wraps
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)

# CONNECT TO DB --> local db 'sqlite:///blog.db'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///blog.db")  # run locally as backup
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Flask-Login Manager
login_manager = LoginManager()
login_manager.init_app(app)


# CONFIGURE TABLES

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))

    # One to Many bidirectional relationship between User(ONE) --> BlogPost(Many)
    # This will act like a List of BlogPost objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)

    # One to Many bidirectional relationship between User(ONE) --> BlogPost(Many)
    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    # Create reference to the User object, the "posts" refers to the posts property in the User class.
    author = relationship("User", back_populates="posts")

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # ***************Parent Relationship*************#
    comments = relationship("Comment", back_populates="parent_post")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)

    # One to Many bidirectional relationship between User(ONE) --> BlogPost(Many)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    comment_author = relationship("User", back_populates="comments")

    # ***************Child Relationship*************#
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")
    text = db.Column(db.Text, nullable=False)


db.create_all()

# create custom decorator
def admin_only(function):
    @wraps(function)
    def wrapper_function(*args, **kwargs):
        print(current_user.get_id())
        if current_user.get_id() != "1":
            return abort(403)
        else:
            return function(*args, **kwargs)

    return wrapper_function


# initialize gravatar
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["GET", "POST"])
def register():
    error = None
    form = RegisterUserForm()

    if form.validate_on_submit():

        try:

            salted_hashed_password = generate_password_hash(password=form.password.data,
                                                            method="pbkdf2:sha256",
                                                            salt_length=8)
            new_user = User(email=form.email.data,
                            password=salted_hashed_password,
                            name=form.name.data
                            )

            db.session.add(new_user)
            db.session.commit()

            login_user(new_user)

            return redirect(url_for("get_all_posts"))

        except exc.SQLAlchemyError:

            error = "Email already exists, please pick another."

    return render_template("register.html", form=form, error=error)


@app.route('/login', methods=["GET", "POST"])
def login():
    error = None

    form = LoginUserForm()

    if form.validate_on_submit():

        try:

            email = form.email.data
            user = User.query.filter_by(email=email).first()
            no_hash_password = form.password.data

            if check_password_hash(pwhash=user.password, password=no_hash_password):

                login_user(user)

                return redirect(url_for("get_all_posts"))

            else:

                error = "Invalid Password"

        except AttributeError:

            error = "Invalid Credentials"

    return render_template("login.html", form=form, error=error)


@app.route('/logout')
def logout():
    logout_user()

    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
@login_required
def show_post(post_id):
    form = CommentForm()

    requested_post = BlogPost.query.get(post_id)

    if form.validate_on_submit():
        new_comment = Comment(
            text=form.comment.data,
            comment_author=current_user,
            parent_post=requested_post
        )

        db.session.add(new_comment)
        db.session.commit()

    return render_template("post.html", post=requested_post, form=form)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>")
def edit_post(post_id):

    post = BlogPost.query.get(post_id)

    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )

    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()

        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
def delete_post(post_id):

    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()

    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(debug=True)
