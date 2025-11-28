import json
from pathlib import Path
from typing import Sequence, Union

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    EmbeddedResource,
    GetPromptResult,
    ImageContent,
    Prompt,
    PromptMessage,
    Resource,
    ResourceTemplate,
    TextContent,
    Tool,
)


class LibraryManagement:
    def __init__(self, books_path: Path):
        self.books_path = books_path
        if not books_path.exists():
            books_path.write_text("[]", encoding="utf-8")
        self.books = json.loads(books_path.read_text(encoding="utf-8"))

    def save_books(self):
        self.books_path.write_text(json.dumps(self.books, indent=4), encoding="utf-8")

    def add_book(self, book: dict) -> str:
        if any(b["isbn"] == book["isbn"].strip() for b in self.books):
            return f"Book with ISBN {book['isbn']} already exists."
        if not all([book.get("title", "").strip(), book.get("author", "").strip(), book.get("isbn", "").strip()]):
            return "Title, author, and ISBN cannot be empty."

        clean_tags = [t.strip() for t in book.get("tags", []) if isinstance(t, str) and t.strip()]
        self.books.append(
            {
                "title": book["title"].strip(),
                "author": book["author"].strip(),
                "isbn": book["isbn"].strip(),
                "tags": clean_tags,
            }
        )
        self.save_books()
        return f"Book '{book['title']}' by '{book['author']}' added successfully."

    def remove_book(self, isbn: str) -> str:
        updated = [b for b in self.books if b["isbn"] != isbn.strip()]
        if len(updated) == len(self.books):
            return f"No book found with ISBN {isbn}."
        self.books = updated
        self.save_books()
        return f"Book with ISBN {isbn} removed successfully."

    def get_num_books(self) -> int:
        return len(self.books)

    def get_all_books(self) -> list:
        return self.books

    def get_book_by_index(self, index: int) -> dict:
        if 0 <= index < len(self.books):
            return self.books[index]
        return {"error": "Book not found."}

    def get_book_by_isbn(self, isbn: str) -> dict:
        for b in self.books:
            if b["isbn"] == isbn.strip():
                return b
        return {"error": "Book not found."}

    def get_suggesting_random_book_prompt(self) -> str:
        return "Suggest a random book from the library. The suggestion should include the title, author, and a brief description."

    def get_suggesting_book_title_by_abstract_prompt(self, abstract: str) -> str:
        return f"Suggest a memorable, descriptive title for a book based on the following abstract: {abstract}"

    def get_analyzing_book_messages(self, book: dict, query: str) -> list[dict[str, str]]:
        return [
            {"role": "user", "content": "This is the book I want to analyze: " + json.dumps(book)},
            {"role": "assistant", "content": "Sure! Let's analyze this book together. What would you like to know?"},
            {"role": "user", "content": query},
        ]


async def serve() -> None:
    book_path = Path("book.json")
    library = LibraryManagement(book_path)
    server = Server("mcp-library")

    # === TOOLS ===
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="add_book",
                description="Add a new book to the library.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "author": {"type": "string"},
                        "isbn": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "author", "isbn"],
                },
            ),
            Tool(
                name="remove_book",
                description="Remove a book by ISBN.",
                inputSchema={
                    "type": "object",
                    "properties": {"isbn": {"type": "string"}},
                    "required": ["isbn"],
                },
            ),
            Tool(name="get_num_books", description="Get total number of books.", inputSchema={"type": "object"}),
            Tool(name="get_all_books", description="List all books.", inputSchema={"type": "object"}),
            Tool(
                name="get_book_by_index",
                description="Get book details by index.",
                inputSchema={
                    "type": "object",
                    "properties": {"index": {"type": "integer"}},
                    "required": ["index"],
                },
            ),
            Tool(
                name="get_book_by_isbn",
                description="Get book details by ISBN.",
                inputSchema={
                    "type": "object",
                    "properties": {"isbn": {"type": "string"}},
                    "required": ["isbn"],
                },
            ),
            Tool(name="get_suggesting_random_book_prompt", description="Prompt for random book.", inputSchema={"type": "object"}),
            Tool(
                name="get_suggesting_book_title_by_abstract_prompt",
                description="Prompt for suggesting a title from abstract.",
                inputSchema={
                    "type": "object",
                    "properties": {"abstract": {"type": "string"}},
                    "required": ["abstract"],
                },
            ),
            Tool(
                name="get_analyzing_book_messages",
                description="Get analysis conversation for a book.",
                inputSchema={
                    "type": "object",
                    "properties": {"book": {"type": "object"}, "query": {"type": "string"}},
                    "required": ["book", "query"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> Sequence[Union[TextContent, ImageContent, EmbeddedResource]]:
        if name == "add_book":
            return [TextContent(type="text", text=library.add_book(arguments))]
        elif name == "remove_book":
            return [TextContent(type="text", text=library.remove_book(arguments["isbn"]))]
        elif name == "get_num_books":
            return [TextContent(type="text", text=str(library.get_num_books()))]
        elif name == "get_all_books":
            return [TextContent(type="text", text=json.dumps(library.get_all_books(), indent=4))]
        elif name == "get_book_by_index":
            return [TextContent(type="text", text=json.dumps(library.get_book_by_index(arguments["index"]), indent=4))]
        elif name == "get_book_by_isbn":
            return [TextContent(type="text", text=json.dumps(library.get_book_by_isbn(arguments["isbn"]), indent=4))]
        elif name == "get_suggesting_random_book_prompt":
            return [TextContent(type="text", text=library.get_suggesting_random_book_prompt())]
        elif name == "get_suggesting_book_title_by_abstract_prompt":
            return [TextContent(type="text", text=library.get_suggesting_book_title_by_abstract_prompt(arguments["abstract"]))]
        elif name == "get_analyzing_book_messages":
            return [TextContent(type="text", text=json.dumps(library.get_analyzing_book_messages(arguments["book"], arguments["query"]), indent=4))]
        else:
            return [TextContent(type="text", text=f"Tool {name} not found.")]

    # === RESOURCES ===
    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                type="text",
                name="library_info",
                description="Information about the library system.",
                embedded=EmbeddedResource(
                    content=TextContent(
                        type="text",
                        text="This system lets you add, remove, and query books. It also provides suggestions."
                    )
                ),
            )
        ]

    @server.read_resource()
    async def read_resource(name: str) -> Union[TextContent, ImageContent, EmbeddedResource]:
        if name == "library_info":
            return TextContent(
                type="text",
                text="This is a library management system that allows you to add, remove, and query books."
            )
        return TextContent(type="text", text=f"Resource {name} not found.")

    # === PROMPTS ===
    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        return [
            Prompt(
                name="book_suggestion",
                description="Suggest a random book.",
                arguments={},
            ),
            Prompt(
                name="book_title_suggestion",
                description="Suggest a book title from abstract.",
                arguments={"abstract": "string"},
            ),
        ]

    @server.get_prompt()
    async def get_prompt(prompt: Prompt) -> GetPromptResult:
        if prompt.name == "book_suggestion":
            return GetPromptResult(
                messages=[
                    PromptMessage(role="system", content=TextContent(type="text", text="You suggest books.")),
                    PromptMessage(role="user", content=TextContent(type="text", text=library.get_suggesting_random_book_prompt())),
                ]
            )
        elif prompt.name == "book_title_suggestion":
            abstract = prompt.arguments.get("abstract", "")
            return GetPromptResult(
                messages=[
                    PromptMessage(role="system", content=TextContent(type="text", text="You create book titles.")),
                    PromptMessage(role="user", content=TextContent(type="text", text=library.get_suggesting_book_title_by_abstract_prompt(abstract))),
                ]
            )
        return GetPromptResult(messages=[])

    options = server.create_initialization_options()
    print(f"MCP Library Server is running with options: {options}")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)


if __name__ == "__main__":
    import asyncio
    asyncio.run(serve())
