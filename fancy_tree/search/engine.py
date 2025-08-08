"""Smart search and filtering engine for fancy-tree."""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable, Union, Set
from difflib import SequenceMatcher

from ..schema import Symbol, SymbolType, FileInfo, RepoSummary


class SearchType(Enum):
    """Types of search operations."""
    FUZZY = "fuzzy"
    REGEX = "regex"
    EXACT = "exact"
    SEMANTIC = "semantic"
    WILDCARD = "wildcard"


class FilterOperator(Enum):
    """Filter comparison operators."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES = "matches"
    IN = "in"
    NOT_IN = "not_in"


@dataclass
class FilterCriteria:
    """Represents a single filter criterion."""
    field: str  # e.g., 'parameter_count', 'name', 'type', 'has_docstring'
    operator: FilterOperator
    value: Any
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator.value,
            "value": self.value,
            "description": self.description
        }


@dataclass
class SearchFilter:
    """Collection of filter criteria with logical operations."""
    criteria: List[FilterCriteria] = field(default_factory=list)
    logic: str = "AND"  # "AND" or "OR"
    name: Optional[str] = None
    description: Optional[str] = None
    
    def add_criterion(self, field: str, operator: FilterOperator, value: Any, description: Optional[str] = None):
        """Add a filter criterion."""
        self.criteria.append(FilterCriteria(field, operator, value, description))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "criteria": [c.to_dict() for c in self.criteria],
            "logic": self.logic,
            "name": self.name,
            "description": self.description
        }


@dataclass
class SearchResult:
    """Represents a search result with relevance scoring."""
    symbol: Symbol
    file_path: str
    file_language: str
    relevance_score: float
    match_type: SearchType
    match_details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol.to_dict(),
            "file_path": self.file_path,
            "file_language": self.file_language,
            "relevance_score": self.relevance_score,
            "match_type": self.match_type.value,
            "match_details": self.match_details
        }


class SearchEngine:
    """Advanced search and filtering engine for code symbols."""
    
    def __init__(self):
        self.fuzzy_threshold = 0.6  # Minimum similarity for fuzzy matching
        self.max_results = 1000  # Maximum results to return
        
        # Predefined common filters
        self.common_filters = self._create_common_filters()
    
    def search(
        self,
        repo_summary: RepoSummary,
        query: str,
        search_type: SearchType = SearchType.FUZZY,
        filters: Optional[List[SearchFilter]] = None,
        target_types: Optional[List[SymbolType]] = None,
        target_languages: Optional[List[str]] = None,
        max_results: Optional[int] = None
    ) -> List[SearchResult]:
        """
        Perform a comprehensive search across the repository.
        
        Args:
            repo_summary: Repository data to search
            query: Search query string
            search_type: Type of search to perform
            filters: Additional filters to apply
            target_types: Symbol types to include (None for all)
            target_languages: Languages to include (None for all)
            max_results: Maximum results to return
        
        Returns:
            List of search results sorted by relevance
        """
        if max_results is None:
            max_results = self.max_results
        
        # Collect all symbols from the repository
        all_symbols = self._collect_symbols(repo_summary, target_languages, target_types)
        
        # Perform the search
        results = []
        
        if search_type == SearchType.FUZZY:
            results = self._fuzzy_search(all_symbols, query)
        elif search_type == SearchType.REGEX:
            results = self._regex_search(all_symbols, query)
        elif search_type == SearchType.EXACT:
            results = self._exact_search(all_symbols, query)
        elif search_type == SearchType.SEMANTIC:
            results = self._semantic_search(all_symbols, query)
        elif search_type == SearchType.WILDCARD:
            results = self._wildcard_search(all_symbols, query)
        
        # Apply filters
        if filters:
            results = self._apply_filters(results, filters)
        
        # Sort by relevance and limit results
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:max_results]
    
    def filter_symbols(
        self,
        repo_summary: RepoSummary,
        filters: List[SearchFilter],
        target_types: Optional[List[SymbolType]] = None,
        target_languages: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """
        Filter symbols without a search query.
        
        Args:
            repo_summary: Repository data to filter
            filters: Filters to apply
            target_types: Symbol types to include
            target_languages: Languages to include
        
        Returns:
            List of filtered results
        """
        # Collect all symbols
        all_symbols = self._collect_symbols(repo_summary, target_languages, target_types)
        
        # Convert to search results with neutral relevance
        results = [
            SearchResult(
                symbol=symbol_data['symbol'],
                file_path=symbol_data['file_path'],
                file_language=symbol_data['file_language'],
                relevance_score=1.0,
                match_type=SearchType.EXACT
            )
            for symbol_data in all_symbols
        ]
        
        # Apply filters
        return self._apply_filters(results, filters)
    
    def get_common_filter(self, name: str) -> Optional[SearchFilter]:
        """Get a predefined common filter by name."""
        return self.common_filters.get(name)
    
    def list_common_filters(self) -> Dict[str, str]:
        """List all available common filters with descriptions."""
        return {name: f.description or name for name, f in self.common_filters.items()}
    
    def _collect_symbols(
        self,
        repo_summary: RepoSummary,
        target_languages: Optional[List[str]] = None,
        target_types: Optional[List[SymbolType]] = None
    ) -> List[Dict[str, Any]]:
        """Collect all symbols from the repository with metadata."""
        symbols = []
        
        def collect_from_directory(dir_info):
            for file_info in dir_info.files:
                # Filter by language
                if target_languages and file_info.language not in target_languages:
                    continue
                
                # Collect symbols from file
                for symbol in file_info.symbols:
                    self._collect_symbol_recursive(
                        symbol, file_info.path, file_info.language, symbols, target_types
                    )
            
            # Process subdirectories
            for subdir in dir_info.subdirs:
                collect_from_directory(subdir)
        
        collect_from_directory(repo_summary.structure)
        return symbols
    
    def _collect_symbol_recursive(
        self,
        symbol: Symbol,
        file_path: str,
        file_language: str,
        symbols: List[Dict[str, Any]],
        target_types: Optional[List[SymbolType]] = None
    ):
        """Recursively collect symbols and their children."""
        # Filter by type
        if target_types is None or symbol.type in target_types:
            symbols.append({
                'symbol': symbol,
                'file_path': file_path,
                'file_language': file_language
            })
        
        # Collect children
        for child in symbol.children:
            self._collect_symbol_recursive(child, file_path, file_language, symbols, target_types)
    
    def _fuzzy_search(self, symbols: List[Dict[str, Any]], query: str) -> List[SearchResult]:
        """Perform fuzzy search on symbol names."""
        results = []
        query_lower = query.lower()
        
        for symbol_data in symbols:
            symbol = symbol_data['symbol']
            
            # Calculate similarity for name
            name_similarity = SequenceMatcher(None, query_lower, symbol.name.lower()).ratio()
            
            # Calculate similarity for signature if available
            signature_similarity = 0.0
            if symbol.signature:
                signature_similarity = SequenceMatcher(None, query_lower, symbol.signature.lower()).ratio()
            
            # Use the best similarity score
            best_similarity = max(name_similarity, signature_similarity)
            
            if best_similarity >= self.fuzzy_threshold:
                results.append(SearchResult(
                    symbol=symbol,
                    file_path=symbol_data['file_path'],
                    file_language=symbol_data['file_language'],
                    relevance_score=best_similarity,
                    match_type=SearchType.FUZZY,
                    match_details={
                        'name_similarity': name_similarity,
                        'signature_similarity': signature_similarity,
                        'query': query
                    }
                ))
        
        return results
    
    def _regex_search(self, symbols: List[Dict[str, Any]], pattern: str) -> List[SearchResult]:
        """Perform regex search on symbol names and signatures."""
        results = []
        
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
        
        for symbol_data in symbols:
            symbol = symbol_data['symbol']
            
            # Search in name
            name_match = regex.search(symbol.name)
            signature_match = None
            
            # Search in signature if available
            if symbol.signature:
                signature_match = regex.search(symbol.signature)
            
            if name_match or signature_match:
                # Calculate relevance based on match position and length
                relevance = 1.0
                if name_match:
                    relevance += (1.0 - name_match.start() / len(symbol.name)) * 0.5
                if signature_match:
                    relevance += 0.3
                
                results.append(SearchResult(
                    symbol=symbol,
                    file_path=symbol_data['file_path'],
                    file_language=symbol_data['file_language'],
                    relevance_score=relevance,
                    match_type=SearchType.REGEX,
                    match_details={
                        'pattern': pattern,
                        'name_match': name_match.group() if name_match else None,
                        'signature_match': signature_match.group() if signature_match else None
                    }
                ))
        
        return results
    
    def _exact_search(self, symbols: List[Dict[str, Any]], query: str) -> List[SearchResult]:
        """Perform exact search on symbol names."""
        results = []
        
        for symbol_data in symbols:
            symbol = symbol_data['symbol']
            
            if symbol.name == query:
                results.append(SearchResult(
                    symbol=symbol,
                    file_path=symbol_data['file_path'],
                    file_language=symbol_data['file_language'],
                    relevance_score=1.0,
                    match_type=SearchType.EXACT,
                    match_details={'query': query}
                ))
        
        return results
    
    def _semantic_search(self, symbols: List[Dict[str, Any]], query: str) -> List[SearchResult]:
        """Perform semantic search based on function signatures and context."""
        results = []
        query_lower = query.lower()
        
        # Extract semantic keywords from query
        semantic_keywords = self._extract_semantic_keywords(query_lower)
        
        for symbol_data in symbols:
            symbol = symbol_data['symbol']
            
            # Calculate semantic relevance
            relevance = 0.0
            match_details = {'query': query, 'matched_keywords': []}
            
            # Check symbol name for semantic matches
            name_lower = symbol.name.lower()
            for keyword in semantic_keywords:
                if keyword in name_lower:
                    relevance += 0.3
                    match_details['matched_keywords'].append(keyword)
            
            # Check signature for semantic matches
            if symbol.signature:
                signature_lower = symbol.signature.lower()
                for keyword in semantic_keywords:
                    if keyword in signature_lower:
                        relevance += 0.2
                        if keyword not in match_details['matched_keywords']:
                            match_details['matched_keywords'].append(keyword)
            
            # Boost relevance for symbol type matches
            if symbol.type.value.lower() in query_lower:
                relevance += 0.4
                match_details['matched_keywords'].append(symbol.type.value)
            
            # Check for parameter-related queries
            if symbol.signature and any(param_word in query_lower for param_word in ['param', 'arg', 'parameter']):
                param_count = symbol.signature.count(',') + 1 if '(' in symbol.signature else 0
                if param_count > 0:
                    relevance += 0.2
                    match_details['parameter_count'] = param_count
            
            if relevance > 0:
                results.append(SearchResult(
                    symbol=symbol,
                    file_path=symbol_data['file_path'],
                    file_language=symbol_data['file_language'],
                    relevance_score=relevance,
                    match_type=SearchType.SEMANTIC,
                    match_details=match_details
                ))
        
        return results
    
    def _wildcard_search(self, symbols: List[Dict[str, Any]], pattern: str) -> List[SearchResult]:
        """Perform wildcard search using glob-style patterns."""
        results = []
        
        # Convert wildcard pattern to regex
        regex_pattern = pattern.replace('*', '.*').replace('?', '.')
        regex_pattern = f"^{regex_pattern}$"
        
        try:
            regex = re.compile(regex_pattern, re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid wildcard pattern: {e}")
        
        for symbol_data in symbols:
            symbol = symbol_data['symbol']
            
            if regex.match(symbol.name):
                results.append(SearchResult(
                    symbol=symbol,
                    file_path=symbol_data['file_path'],
                    file_language=symbol_data['file_language'],
                    relevance_score=1.0,
                    match_type=SearchType.WILDCARD,
                    match_details={'pattern': pattern}
                ))
        
        return results
    
    def _extract_semantic_keywords(self, query: str) -> List[str]:
        """Extract semantic keywords from a search query."""
        # Common programming concepts and patterns
        semantic_patterns = {
            'getter': ['get', 'fetch', 'retrieve', 'obtain'],
            'setter': ['set', 'update', 'modify', 'change'],
            'creator': ['create', 'make', 'build', 'generate', 'new'],
            'validator': ['validate', 'check', 'verify', 'test'],
            'converter': ['convert', 'transform', 'parse', 'format'],
            'handler': ['handle', 'process', 'manage', 'deal'],
            'utility': ['util', 'helper', 'tool', 'common'],
            'database': ['db', 'database', 'sql', 'query', 'table'],
            'network': ['http', 'api', 'request', 'response', 'client', 'server'],
            'file': ['file', 'path', 'directory', 'folder', 'io'],
            'string': ['str', 'string', 'text', 'char'],
            'number': ['int', 'float', 'number', 'numeric', 'math'],
            'collection': ['list', 'array', 'dict', 'map', 'set', 'collection']
        }
        
        keywords = []
        words = query.split()
        
        for word in words:
            keywords.append(word)
            # Add related semantic keywords
            for category, related_words in semantic_patterns.items():
                if word in related_words:
                    keywords.extend(related_words)
        
        return list(set(keywords))  # Remove duplicates
    
    def _apply_filters(self, results: List[SearchResult], filters: List[SearchFilter]) -> List[SearchResult]:
        """Apply filters to search results."""
        filtered_results = results
        
        for search_filter in filters:
            filtered_results = self._apply_single_filter(filtered_results, search_filter)
        
        return filtered_results
    
    def _apply_single_filter(self, results: List[SearchResult], search_filter: SearchFilter) -> List[SearchResult]:
        """Apply a single filter to search results."""
        if not search_filter.criteria:
            return results
        
        filtered_results = []
        
        for result in results:
            if search_filter.logic == "AND":
                # All criteria must match
                if all(self._evaluate_criterion(result, criterion) for criterion in search_filter.criteria):
                    filtered_results.append(result)
            else:  # OR logic
                # At least one criterion must match
                if any(self._evaluate_criterion(result, criterion) for criterion in search_filter.criteria):
                    filtered_results.append(result)
        
        return filtered_results
    
    def _evaluate_criterion(self, result: SearchResult, criterion: FilterCriteria) -> bool:
        """Evaluate a single filter criterion against a search result."""
        # Get the field value from the result
        field_value = self._get_field_value(result, criterion.field)
        
        if field_value is None:
            return False
        
        # Apply the operator
        if criterion.operator == FilterOperator.EQUALS:
            return field_value == criterion.value
        elif criterion.operator == FilterOperator.NOT_EQUALS:
            return field_value != criterion.value
        elif criterion.operator == FilterOperator.GREATER_THAN:
            return field_value > criterion.value
        elif criterion.operator == FilterOperator.LESS_THAN:
            return field_value < criterion.value
        elif criterion.operator == FilterOperator.GREATER_EQUAL:
            return field_value >= criterion.value
        elif criterion.operator == FilterOperator.LESS_EQUAL:
            return field_value <= criterion.value
        elif criterion.operator == FilterOperator.CONTAINS:
            return criterion.value in str(field_value)
        elif criterion.operator == FilterOperator.NOT_CONTAINS:
            return criterion.value not in str(field_value)
        elif criterion.operator == FilterOperator.STARTS_WITH:
            return str(field_value).startswith(str(criterion.value))
        elif criterion.operator == FilterOperator.ENDS_WITH:
            return str(field_value).endswith(str(criterion.value))
        elif criterion.operator == FilterOperator.MATCHES:
            try:
                return bool(re.search(str(criterion.value), str(field_value), re.IGNORECASE))
            except re.error:
                return False
        elif criterion.operator == FilterOperator.IN:
            return field_value in criterion.value
        elif criterion.operator == FilterOperator.NOT_IN:
            return field_value not in criterion.value
        
        return False
    
    def _get_field_value(self, result: SearchResult, field: str) -> Any:
        """Get a field value from a search result."""
        symbol = result.symbol
        
        # Direct symbol fields
        if field == "name":
            return symbol.name
        elif field == "type":
            return symbol.type.value
        elif field == "line":
            return symbol.line
        elif field == "signature":
            return symbol.signature
        elif field == "language":
            return symbol.language or result.file_language
        elif field == "file_path":
            return result.file_path
        elif field == "relevance_score":
            return result.relevance_score
        
        # Derived fields
        elif field == "parameter_count":
            return self._count_parameters(symbol.signature) if symbol.signature else 0
        elif field == "has_parameters":
            return self._count_parameters(symbol.signature) > 0 if symbol.signature else False
        elif field == "has_return_type":
            return "->" in symbol.signature if symbol.signature else False
        elif field == "is_private":
            return symbol.name.startswith("_")
        elif field == "is_public":
            return not symbol.name.startswith("_")
        elif field == "has_docstring":
            # This would need to be enhanced with actual docstring detection
            return False  # Placeholder
        elif field == "name_length":
            return len(symbol.name)
        elif field == "signature_length":
            return len(symbol.signature) if symbol.signature else 0
        elif field == "child_count":
            return len(symbol.children)
        elif field == "has_children":
            return len(symbol.children) > 0
        
        return None
    
    def _count_parameters(self, signature: str) -> int:
        """Count parameters in a function signature."""
        if not signature or '(' not in signature:
            return 0
        
        # Extract parameter list
        start = signature.find('(')
        end = signature.find(')', start)
        if end == -1:
            return 0
        
        param_str = signature[start+1:end].strip()
        if not param_str:
            return 0
        
        # Simple parameter counting (could be enhanced for complex signatures)
        return len([p.strip() for p in param_str.split(',') if p.strip()])
    
    def _create_common_filters(self) -> Dict[str, SearchFilter]:
        """Create predefined common filters."""
        filters = {}
        
        # Functions with many parameters
        many_params = SearchFilter(name="many_parameters", description="Functions with more than 5 parameters")
        many_params.add_criterion("type", FilterOperator.IN, ["function", "method"])
        many_params.add_criterion("parameter_count", FilterOperator.GREATER_THAN, 5)
        filters["many_parameters"] = many_params
        
        # Large functions (by name length as proxy)
        large_functions = SearchFilter(name="large_functions", description="Functions with long names (potential complexity indicator)")
        large_functions.add_criterion("type", FilterOperator.IN, ["function", "method"])
        large_functions.add_criterion("name_length", FilterOperator.GREATER_THAN, 20)
        filters["large_functions"] = large_functions
        
        # Private methods
        private_methods = SearchFilter(name="private_methods", description="Private methods and functions")
        private_methods.add_criterion("type", FilterOperator.IN, ["function", "method"])
        private_methods.add_criterion("is_private", FilterOperator.EQUALS, True)
        filters["private_methods"] = private_methods
        
        # Public methods
        public_methods = SearchFilter(name="public_methods", description="Public methods and functions")
        public_methods.add_criterion("type", FilterOperator.IN, ["function", "method"])
        public_methods.add_criterion("is_public", FilterOperator.EQUALS, True)
        filters["public_methods"] = public_methods
        
        # Classes only
        classes_only = SearchFilter(name="classes_only", description="Class definitions only")
        classes_only.add_criterion("type", FilterOperator.EQUALS, "class")
        filters["classes_only"] = classes_only
        
        # Functions only
        functions_only = SearchFilter(name="functions_only", description="Function definitions only")
        functions_only.add_criterion("type", FilterOperator.IN, ["function", "method"])
        filters["functions_only"] = functions_only
        
        # Functions with return types
        typed_functions = SearchFilter(name="typed_functions", description="Functions with return type annotations")
        typed_functions.add_criterion("type", FilterOperator.IN, ["function", "method"])
        typed_functions.add_criterion("has_return_type", FilterOperator.EQUALS, True)
        filters["typed_functions"] = typed_functions
        
        # Functions without parameters
        no_param_functions = SearchFilter(name="no_param_functions", description="Functions without parameters")
        no_param_functions.add_criterion("type", FilterOperator.IN, ["function", "method"])
        no_param_functions.add_criterion("parameter_count", FilterOperator.EQUALS, 0)
        filters["no_param_functions"] = no_param_functions
        
        # Symbols with children (classes with methods, etc.)
        parent_symbols = SearchFilter(name="parent_symbols", description="Symbols that contain other symbols")
        parent_symbols.add_criterion("has_children", FilterOperator.EQUALS, True)
        filters["parent_symbols"] = parent_symbols
        
        return filters


def create_search_engine() -> SearchEngine:
    """Factory function to create a configured search engine."""
    return SearchEngine()


# Utility functions for common search patterns
def search_by_name(repo_summary: RepoSummary, name: str, fuzzy: bool = True) -> List[SearchResult]:
    """Quick search by symbol name."""
    engine = create_search_engine()
    search_type = SearchType.FUZZY if fuzzy else SearchType.EXACT
    return engine.search(repo_summary, name, search_type)


def search_functions_with_many_params(repo_summary: RepoSummary, min_params: int = 5) -> List[SearchResult]:
    """Find functions with many parameters."""
    engine = create_search_engine()
    filter_obj = SearchFilter()
    filter_obj.add_criterion("type", FilterOperator.IN, ["function", "method"])
    filter_obj.add_criterion("parameter_count", FilterOperator.GREATER_EQUAL, min_params)
    
    return engine.filter_symbols(repo_summary, [filter_obj])


def search_by_pattern(repo_summary: RepoSummary, pattern: str) -> List[SearchResult]:
    """Search using regex pattern."""
    engine = create_search_engine()
    return engine.search(repo_summary, pattern, SearchType.REGEX)


def search_classes_without_methods(repo_summary: RepoSummary) -> List[SearchResult]:
    """Find classes without methods."""
    engine = create_search_engine()
    filter_obj = SearchFilter()
    filter_obj.add_criterion("type", FilterOperator.EQUALS, "class")
    filter_obj.add_criterion("child_count", FilterOperator.EQUALS, 0)
    
    return engine.filter_symbols(repo_summary, [filter_obj])
