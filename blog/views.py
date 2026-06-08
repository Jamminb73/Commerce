from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from .forms import PostForm
from .models import Post

@staff_member_required
def admin_dashboard(request):
    """
    Secure command center for the blog.
    Fetches all posts and splits them into clean pages of 5.
    """
    posts_list = Post.objects.all().order_by('-created_at')
    
    # Set up Paginator: 5 posts per page
    paginator = Paginator(posts_list, 5) 
    
    # Get the current page number from the URL string
    page_number = request.GET.get('page')
    
    # Fetch the specific 5 posts for this page
    posts = paginator.get_page(page_number)
    
    return render(request, 'blog/dashboard.html', {'posts': posts})

@staff_member_required
def create_post(request):
    """
    Handles rendering the creation form and saving 
    new blog entries into the database.
    """
    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('blog:admin_dashboard')
    else:
        form = PostForm()
    
    return render(request, 'blog/create_post.html', {'form': form})